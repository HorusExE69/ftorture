/* ************************************************************************** */
/*  Replay harness for `torture <project> <dir> --repro FILE#IDX[mK]`.        */
/*                                                                            */
/*  Same API as engine.c + memtrack.c (zft.h), but it runs ONE test of ONE    */
/*  test file directly in main(): no fork, no electric-fence malloc, so       */
/*  valgrind and gdb follow your code. Test data (gstr, gmem, gbuf) still     */
/*  sits right before a forbidden page, so out-of-bounds reads still crash.   */
/*  With mK, the K-th malloc between ARM() and DISARM() returns NULL.         */
/*                                                                            */
/*  usage: repro IDX [FAIL_AT] [SEED]                                         */
/* ************************************************************************** */
#define _GNU_SOURCE
#include <errno.h>
#include <signal.h>
#include <stdarg.h>
#include <sys/mman.h>
#include "zft.h"

void	*__real_malloc(size_t n);
void	__real_free(void *p);

int		g_ref;
int		g_fail_at;
int		g_armed;
static int		g_armed_count;
static char		g_input[1024];
static t_test	g_tests[512];
static int		g_ntests;

volatile long	g_bench_sink;
t_cost			g_bench_cost;
double			g_score_ideal;
double			g_score_real;

static int	en(void)
{
	const char	*l = getenv("FTORTURE_LANG");

	return (l && !strcmp(l, "en"));
}
#define M(fr, e) (en() ? (e) : (fr))

int	zft_en(void)
{
	return (en());
}

const char	*zft_path(void)
{
	const char	*p = getenv("FTORTURE_REPRO_PATH");

	return (p ? p : ".");
}

/* ------------------------------------------------------------ registry -- */
void	zft_register(const char *func, const char *name, t_kind kind, int spec,
			void (*fn)(void), const char *file, int line, int idx)
{
	if (g_ntests < 512)
	{
		int	seq = g_ntests++;

		g_tests[seq] = (t_test){func, name, kind, spec, fn, file, line,
			seq + 1, idx};
	}
}

void	zft_bench_register(const char *f, void (*fn)(long), const char *file,
			int line)
{
	(void)f;
	(void)fn;
	(void)file;
	(void)line;
}

void	zft_score_register(const char *f, void (*fn)(void), const char *file,
			int line)
{
	(void)f;
	(void)fn;
	(void)file;
	(void)line;
}

/* ------------------------------------------------- allocation tracking -- */
#define TAB (1u << 18)

static struct s_blk
{
	void	*p;
	size_t	n;
	int		live;
}	g_tab[TAB];

static unsigned	hidx(const void *p)
{
	return ((unsigned)(((uintptr_t)p * 0x9E3779B97F4A7C15ULL) >> 46) & (TAB - 1));
}

void	*__wrap_malloc(size_t n)
{
	void		*p;
	unsigned	i;

	if (g_armed && ++g_armed_count == g_fail_at && g_fail_at)
	{
		fprintf(stderr, M("\n[ftorture] malloc n°%d -> NULL (échec simulé)\n",
			"\n[ftorture] malloc #%d -> NULL (simulated failure)\n"),
			g_armed_count);
		errno = ENOMEM;
		return (NULL);
	}
	p = __real_malloc(n);
	if (!p)
		return (NULL);
	i = hidx(p);
	for (unsigned k = 0; k < 64; k++, i = (i + 1) & (TAB - 1))
		if (!g_tab[i].live)
		{
			g_tab[i] = (struct s_blk){p, n, 1};
			break ;
		}
	return (p);
}

void	__wrap_free(void *p)
{
	unsigned	i = hidx(p);

	if (!p)
		return ;
	for (unsigned k = 0; k < 64; k++, i = (i + 1) & (TAB - 1))
		if (g_tab[i].live && g_tab[i].p == p)
		{
			g_tab[i].live = 0;
			break ;
		}
	__real_free(p);
}

size_t	alloc_size(const void *p)
{
	unsigned	i = hidx(p);

	for (unsigned k = 0; k < 64; k++, i = (i + 1) & (TAB - 1))
		if (g_tab[i].live && g_tab[i].p == p)
			return (g_tab[i].n);
	return ((size_t)-1);
}

int	zm_live_blocks(void)
{
	int	n = 0;

	for (unsigned i = 0; i < TAB; i++)
		n += g_tab[i].live;
	return (n);
}

void	real_free(void *p)
{
	__real_free(p);
}

/* ----------------------------------------------- guarded test buffers -- */
void	*gbuf(size_t n, int fill)
{
	size_t	pg = (size_t)sysconf(_SC_PAGESIZE);
	size_t	len = (n + pg - 1) / pg * pg + pg;
	char	*base;

	base = mmap(NULL, len, PROT_READ | PROT_WRITE,
			MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (base == MAP_FAILED)
		zft_failf(__FILE__, __LINE__, "mmap");
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

int	cap_open(void)
{
	char	path[] = "/tmp/ftorture_capXXXXXX";
	int		fd = mkstemp(path);

	if (fd < 0)
		zft_failf(__FILE__, __LINE__, "mkstemp");
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

/* same generator as memtrack.c: same seed, same inputs */
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

/* --------------------------------------------------------- reporting -- */
void	zft_esc(char *d, size_t dsz, const char *s, size_t n)
{
	size_t	j = 0;
	size_t	i;

	for (i = 0; i < n && j + 8 < dsz; i++)
	{
		unsigned char	c = (unsigned char)s[i];

		if (c == '\n')
			j += (size_t)snprintf(d + j, dsz - j, "\\n");
		else if (c == '\t')
			j += (size_t)snprintf(d + j, dsz - j, "\\t");
		else if (c == '"' || c == '\\')
			j += (size_t)snprintf(d + j, dsz - j, "\\%c", c);
		else if (c < 32 || c >= 127)
			j += (size_t)snprintf(d + j, dsz - j, "\\x%02x", c);
		else
			d[j++] = (char)c;
	}
	if (i < n)
		j += (size_t)snprintf(d + j, dsz - j, "…");
	d[j] = 0;
}

static char	*ring(void)
{
	static char	r[8][1100];
	static int	i;

	return (r[i++ & 7]);
}

const char	*zft_str(const char *s)
{
	char	*b;
	size_t	n;

	if (!s)
		return ("NULL");
	b = ring();
	n = strlen(s);
	b[0] = '"';
	zft_esc(b + 1, 1090, s, n > 300 ? 300 : n);
	strcat(b, "\"");
	return (b);
}

const char	*zft_mem(const void *p, size_t n)
{
	char				*b = ring();
	size_t				j = 0;
	const unsigned char	*c = p;

	if (!p)
		return ("NULL");
	b[0] = 0;
	for (size_t i = 0; i < n && i < 64; i++)
		j += (size_t)snprintf(b + j, 1100 - j, "%02x ", c[i]);
	return (b);
}

void	zft_soft(void)
{
}

static void	show_input(void)
{
	if (g_input[0])
		printf(M("   entrée   %s\n", "   input    %s\n"), g_input);
}

void	zft_fail(const char *file, int line, const char *expr,
			const char *expected, const char *got)
{
	fflush(stdout);
	printf(M("\n\033[1;31m ✘ ÉCHEC\033[0m  %s:%d\n", "\n\033[1;31m ✘ FAIL\033[0m  %s:%d\n"),
		strrchr(file, '/') ? strrchr(file, '/') + 1 : file, line);
	show_input();
	if (expected || got)
	{
		printf("   expr     %s\n", expr);
		printf(M("   attendu  %s\n   obtenu   %s\n",
			"   expected %s\n   actual   %s\n"), expected ? expected : "",
			got ? got : "");
	}
	else
		printf(M("   erreur   %s\n", "   error    %s\n"), expr);
	fflush(stdout);
	exit(1);
}

void	zft_failf(const char *file, int line, const char *fmt, ...)
{
	char	buf[600];
	va_list	ap;

	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	zft_fail(file, line, buf, NULL, NULL);
}

void	zft_out(const char *fmt, ...)
{
	va_list	ap;

	printf(M("   ta fonction a renvoyé : ", "   your function returned: "));
	va_start(ap, fmt);
	vprintf(fmt, ap);
	va_end(ap);
	printf("\n");
}

void	zft_input(const char *fmt, ...)
{
	va_list	ap;

	va_start(ap, fmt);
	vsnprintf(g_input, sizeof(g_input), fmt, ap);
	va_end(ap);
	if (getenv("FTORTURE_REPRO_TRACE"))
		printf("   · %s\n", g_input);
}

/* a crash: say during which input, then die from the same signal so that
   valgrind / gdb show where it happened                                   */
static void	on_signal(int sig)
{
	char	msg[1300];
	int		n;

	n = snprintf(msg, sizeof(msg), M("\n\033[1;31m ✘ CRASH\033[0m  signal %d "
		"(%s)\n", "\n\033[1;31m ✘ CRASH\033[0m  signal %d (%s)\n"), sig,
		sig == SIGALRM ? M("timeout : boucle infinie ?", "timeout: infinite loop?")
		: strsignal(sig));
	if (g_input[0] && n > 0 && (size_t)n < sizeof(msg))
		n += snprintf(msg + n, sizeof(msg) - (size_t)n,
			M("   pendant  %s\n", "   during   %s\n"), g_input);
	if (n > 0)
		(void)!write(1, msg, (size_t)n < sizeof(msg) ? (size_t)n : sizeof(msg));
	signal(sig, SIG_DFL);
	raise(sig);
}

int	main(int ac, char **av)
{
	int		idx;
	t_test	*t = NULL;

	if (ac < 2)
	{
		fprintf(stderr, "usage: %s IDX [FAIL_AT] [SEED]\n", av[0]);
		return (2);
	}
	idx = atoi(av[1]);
	g_fail_at = ac > 2 ? atoi(av[2]) : 0;
	zsrand(ac > 3 ? (uint32_t)strtoul(av[3], NULL, 10) : 42);
	for (int i = 0; i < g_ntests; i++)
		if (g_tests[i].idx == idx)
			t = &g_tests[i];
	if (!t)
	{
		fprintf(stderr, M("test n°%d introuvable dans ce fichier\n",
			"test #%d not found in this file\n"), idx);
		return (2);
	}
	setvbuf(stdout, NULL, _IOLBF, 0);
	printf(M("\n \033[1m▶ « %s »\033[0m  %s:%d\n", "\n \033[1m▶ \"%s\"\033[0m  %s:%d\n"),
		t->name, strrchr(t->file, '/') ? strrchr(t->file, '/') + 1 : t->file,
		t->line);
	if (t->kind == K_VSREF)
		printf(M("   (seule ta fonction est appelée : PICK(ft, ref) -> ft)\n",
			"   (only your function is called: PICK(ft, ref) -> ft)\n"));
	if (g_fail_at)
		printf(M("   (le malloc n°%d entre ARM() et DISARM() renverra NULL)\n",
			"   (malloc #%d between ARM() and DISARM() will return NULL)\n"),
			g_fail_at);
	signal(SIGSEGV, on_signal);
	signal(SIGBUS, on_signal);
	signal(SIGABRT, on_signal);
	signal(SIGFPE, on_signal);
	signal(SIGALRM, on_signal);
	alarm(getenv("FTORTURE_REPRO_GDB") ? 0 : 30);
	t->fn();
	alarm(0);
	g_armed = 0;
	printf(M("\n\033[1;32m ✔ le test se termine sans échec ici\033[0m\n",
		"\n\033[1;32m ✔ the test ends without failure here\033[0m\n"));
	printf(M("   (ftorture détecte en plus les fuites, les octets écrits hors "
		"d'un bloc et les double free :\n    regarde le rapport de valgrind "
		"ci-dessous)\n", "   (ftorture also detects leaks, bytes written "
		"outside a block and double frees:\n    see the valgrind report "
		"below)\n"));
	return (0);
}
