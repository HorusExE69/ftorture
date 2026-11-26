/* ************************************************************************** */
/*  Memory instrumentation (linked with -Wl,--wrap=malloc,--wrap=free).       */
/*                                                                            */
/*  Inside a test process every malloc() gets its own mmap'ed region whose    */
/*  last byte touches a PROT_NONE page ("electric fence"):                    */
/*    - writing/reading 1 byte past the block       -> SIGSEGV                */
/*    - using a block after free() (page protected) -> SIGSEGV                */
/*    - double free / free of a non-malloc pointer  -> reported               */
/*    - blocks still alive at the end of the test   -> leak                   */
/*    - the Nth malloc can be forced to return NULL -> protection tests       */
/*  Note: blocks are byte-aligned at their end, not 16-aligned.               */
/* ************************************************************************** */
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include "zft.h"

void	*__real_malloc(size_t n);
void	__real_free(void *p);

#define TAB_BITS 17
#define TAB (1u << TAB_BITS)

typedef struct s_blk
{
	uintptr_t		user;
	char			*base;
	size_t			maplen;
	size_t			size;
	unsigned char	state;	/* 0 empty, 1 live, 2 freed, 3 freed+unmapped */
}	t_blk;

static t_blk	g_tab[TAB];
static unsigned	g_used;
static unsigned	g_freed_maps;
static uintptr_t	g_lo;	/* address range covered by guarded mappings */
static uintptr_t	g_hi;
static size_t	g_page;

int		g_zm_active;		/* set in the test process only */
int		g_fail_at;
int		g_armed;
int		g_armed_count;
int		g_zm_bad_free;
char	g_zm_bad_msg[160];

static size_t	page(void)
{
	if (!g_page)
		g_page = (size_t)sysconf(_SC_PAGESIZE);
	return (g_page);
}

static unsigned	hidx(uintptr_t p)
{
	return ((unsigned)(((uint64_t)p * 0x9E3779B97F4A7C15ULL) >> (64 - TAB_BITS)));
}

static t_blk	*lookup(uintptr_t p, int create)
{
	unsigned	i = hidx(p);
	unsigned	n = 0;

	while (n++ < TAB)
	{
		if (g_tab[i].state == 0)
		{
			if (!create)
				return (NULL);
			g_used++;
			g_tab[i].user = p;
			return (&g_tab[i]);
		}
		if (g_tab[i].user == p)
			return (&g_tab[i]);
		i = (i + 1) & (TAB - 1);
	}
	return (NULL);
}

void	zm_reset(void)
{
	if (g_used)
		memset(g_tab, 0, sizeof(g_tab));
	g_used = 0;
	g_lo = 0;
	g_hi = 0;
	g_freed_maps = 0;
	g_armed_count = 0;
	g_zm_bad_free = 0;
	g_zm_bad_msg[0] = 0;
}

void	*__wrap_malloc(size_t n)
{
	size_t	pg;
	size_t	len;
	char	*base;
	t_blk	*b;

	if (g_zm_active && g_armed)
	{
		g_armed_count++;
		if (g_fail_at && g_armed_count == g_fail_at)
		{
			errno = ENOMEM;
			return (NULL);
		}
	}
	if (!g_zm_active || g_used > TAB / 4 * 3)
		return (__real_malloc(n));
	if (n > ((size_t)1 << 32))
	{
		errno = ENOMEM;
		return (NULL);
	}
	pg = page();
	len = (n + pg - 1) / pg * pg + pg;
	base = mmap(NULL, len, PROT_READ | PROT_WRITE,
			MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (base == MAP_FAILED)
	{
		errno = ENOMEM;
		return (NULL);
	}
	mprotect(base + len - pg, pg, PROT_NONE);
	b = lookup((uintptr_t)(base + len - pg - n), 1);
	if (!b)
	{
		munmap(base, len);
		return (__real_malloc(n));
	}
	b->base = base;
	b->maplen = len;
	b->size = n;
	b->state = 1;
	if (!g_lo || (uintptr_t)base < g_lo)
		g_lo = (uintptr_t)base;
	if ((uintptr_t)base + len > g_hi)
		g_hi = (uintptr_t)base + len;
	/* malloc is not calloc: poison the block (only both ends of big ones,
	   e.g. a 10 MB BUFFER_SIZE allocated on every call)                  */
	if (n <= 65536)
		memset(base + len - pg - n, 0xA5, n);
	else
	{
		memset(base + len - pg - n, 0xA5, 4096);
		memset(base + len - pg - 4096, 0xA5, 4096);
	}
	return (base + len - pg - n);
}

/* is the page holding p mapped right now? (an unmapped block's address
   range can be handed out again by the libc, e.g. mmap'ed big mallocs)  */
static int	is_mapped(uintptr_t p)
{
	uintptr_t	pg = p & ~(uintptr_t)(page() - 1);
	int			saved = errno;
	int			r;

	r = (msync((void *)pg, page(), MS_ASYNC) == 0 || errno != ENOMEM);
	errno = saved;
	return (r);
}

static int	inside_block(uintptr_t p)
{
	unsigned	i;

	/* fast path: outside every guarded mapping ever made (libc heap...) */
	if (p < g_lo || p >= g_hi)
		return (0);
	for (i = 0; i < TAB; i++)
		if (g_tab[i].state && p > g_tab[i].user
			&& p < (uintptr_t)g_tab[i].base + g_tab[i].maplen
			&& (g_tab[i].state != 3 || !is_mapped(p)))
			return (1);
	return (0);
}

void	__wrap_free(void *p)
{
	t_blk	*b;

	if (!p)
		return ;
	if (!g_zm_active)
	{
		__real_free(p);
		return ;
	}
	b = lookup((uintptr_t)p, 0);
	if (b && b->state == 3 && is_mapped((uintptr_t)p))
		b = NULL;	/* address reused since munmap: not our block anymore */
	if (b && b->state >= 2)
	{
		g_zm_bad_free++;
		snprintf(g_zm_bad_msg, sizeof(g_zm_bad_msg),
			"double free d'un bloc de %zu octet(s)", b->size);
		return ;
	}
	if (b && b->state == 1)
	{
		b->state = 2;
		if (g_freed_maps++ < 20000)
			mprotect(b->base, b->maplen, PROT_NONE);
		else
		{
			munmap(b->base, b->maplen);
			b->state = 3;	/* entry stays, but the range may be reused */
		}
		return ;
	}
	if (inside_block((uintptr_t)p))
	{
		g_zm_bad_free++;
		snprintf(g_zm_bad_msg, sizeof(g_zm_bad_msg),
			"free() d'un pointeur au milieu d'un bloc malloc");
		return ;
	}
	__real_free(p);	/* memory from the libc itself, or from before the fork */
}

void	real_free(void *p)
{
	__real_free(p);
}

size_t	alloc_size(const void *p)
{
	t_blk	*b = lookup((uintptr_t)p, 0);

	if (!b || b->state != 1)
		return ((size_t)-1);
	return (b->size);
}

int	zm_live_blocks(void)
{
	unsigned	i;
	int			n = 0;

	for (i = 0; i < TAB; i++)
		if (g_tab[i].state == 1)
			n++;
	return (n);
}

size_t	zm_live_bytes(void)
{
	unsigned	i;
	size_t		n = 0;

	for (i = 0; i < TAB; i++)
		if (g_tab[i].state == 1)
			n += g_tab[i].size;
	return (n);
}

/* --------------------------------------------------------- guarded data -- */
void	*gbuf(size_t n, int fill)
{
	size_t	pg = page();
	size_t	len = (n + pg - 1) / pg * pg + pg;
	char	*base;

	base = mmap(NULL, len, PROT_READ | PROT_WRITE,
			MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (base == MAP_FAILED)
		zft_failf(__FILE__, __LINE__, "mmap a échoué (tester)");
	mprotect(base + len - pg, pg, PROT_NONE);
	memset(base + len - pg - n, fill, n);
	return (base + len - pg - n);
}

void	*gmem(const void *src, size_t n)
{
	void	*p = gbuf(n, 0);

	memcpy(p, src, n);
	return (p);
}

char	*gstr(const char *s)
{
	return (gmem(s, strlen(s) + 1));
}

/* ----------------------------------------------------------- fd capture -- */
int	cap_open(void)
{
	char	path[] = "/tmp/ftorture_capXXXXXX";
	int		fd = mkstemp(path);

	if (fd < 0)
		zft_failf(__FILE__, __LINE__, "mkstemp a échoué (tester)");
	unlink(path);
	return (fd);
}

const char	*cap_read(int fd, size_t *len)
{
	static char	buf[1 << 16];
	ssize_t		r;
	size_t		tot = 0;

	lseek(fd, 0, SEEK_SET);
	while (tot < sizeof(buf) - 1
		&& (r = read(fd, buf + tot, sizeof(buf) - 1 - tot)) > 0)
		tot += (size_t)r;
	buf[tot] = 0;
	if (len)
		*len = tot;
	return (buf);
}

/* ------------------------------------------------------------------ rng -- */
static uint32_t	g_rng = 0x2545F491u;

void	zsrand(uint32_t seed)
{
	g_rng = seed ? seed : 0x2545F491u;
}

uint32_t	zrand(void)
{
	g_rng ^= g_rng << 13;
	g_rng ^= g_rng >> 17;
	g_rng ^= g_rng << 5;
	return (g_rng);
}
