/* get_next_line tester helpers: temp files, line checking, read() wrapper  */
#include <errno.h>
#include <fcntl.h>
#include "gnl.h"

ssize_t	__real_read(int fd, void *buf, size_t n);

size_t	g_rd_bytes;
int		g_rd_calls;
int		g_rd_fail_at;
int		g_rd_short;

ssize_t	__wrap_read(int fd, void *buf, size_t n)
{
	ssize_t	r;

	g_rd_calls++;
	if (g_rd_fail_at && g_rd_calls == g_rd_fail_at)
	{
		errno = EIO;
		return (-1);
	}
	/* short reads: a regular file may also return fewer bytes than asked */
	if (g_rd_short && n > 1)
		n = 1 + zrand() % n;
	r = __real_read(fd, buf, n);
	if (r > 0)
		g_rd_bytes += (size_t)r;
	return (r);
}

int	gnl_file(const char *data, size_t len)
{
	char	path[] = "/tmp/ftorture_gnlXXXXXX";
	int		w = mkstemp(path);
	int		fd;
	size_t	done = 0;

	if (w < 0)
		zft_failf(__FILE__, __LINE__, "mkstemp a échoué (tester)");
	while (done < len)
	{
		ssize_t	k = write(w, data + done, len - done);

		if (k <= 0)
			zft_failf(__FILE__, __LINE__, "write a échoué (tester)");
		done += (size_t)k;
	}
	close(w);
	fd = open(path, O_RDONLY);
	unlink(path);
	if (fd < 0)
		zft_failf(__FILE__, __LINE__, "open a échoué (tester)");
	return (fd);
}

void	gnl_init(t_gnl *g, int fd, const char *data, size_t len,
			const char *what)
{
	g->fd = fd;
	g->data = data;
	g->len = len;
	g->pos = 0;
	g->line = 1;
	g->done = 0;
	g->what = what;
}

static const char	*bs_str(void)
{
	static char	b[32];

	if (Z_BS < 0)
		return ("défaut");
	snprintf(b, sizeof(b), "%d", Z_BS);
	return (b);
}

static void	show(char *dst, size_t dsz, const char *s, size_t n)
{
	char	esc[900];
	const char *lang = getenv("FTORTURE_LANG");

	zft_esc(esc, sizeof(esc), s, n > 200 ? 200 : n);
	snprintf(dst, dsz, lang && !strcmp(lang, "en")
		? "\"%s%s\" (%zu byte%s)" : "\"%s%s\" (%zu octet%s)",
		esc, n > 200 ? "…" : "", n, n > 1 ? "s" : "");
}

int	gnl_step(const char *file, int line, t_gnl *g)
{
	char	exp[1100];
	char	got[1100];
	char	*r;

	if (g->done)
		return (0);
	INPUT("%s · fd %d · ligne %d · BUFFER_SIZE=%s", g->what, g->fd, g->line,
		bs_str());
	r = get_next_line(g->fd);
	if (g->pos >= g->len)
	{
		if (r)
		{
			show(got, sizeof(got), r, strlen(r));
			zft_fail(file, line, "après la dernière ligne", "NULL", got);
		}
		INPUT("%s · fd %d · appel après NULL · BUFFER_SIZE=%s", g->what,
			g->fd, bs_str());
		r = get_next_line(g->fd);
		if (r)
		{
			show(got, sizeof(got), r, strlen(r));
			zft_fail(file, line, "rappel après la fin du fichier", "NULL", got);
		}
		g->done = 1;
		return (0);
	}
	{
		const char	*nl = memchr(g->data + g->pos, '\n', g->len - g->pos);
		size_t		end = nl ? (size_t)(nl - g->data) + 1 : g->len;
		size_t		elen = end - g->pos;

		show(exp, sizeof(exp), g->data + g->pos, elen);
		if (!r)
			zft_fail(file, line, "NULL renvoyé alors qu'il reste des lignes",
				exp, "NULL");
		if (strlen(r) != elen || memcmp(r, g->data + g->pos, elen) != 0)
		{
			show(got, sizeof(got), r, strlen(r));
			zft_fail(file, line, "ligne différente", exp, got);
		}
		if (alloc_size(r) == (size_t)-1)
			zft_failf(file, line, "la ligne renvoyée n'est pas un bloc alloué "
				"avec malloc (pointeur vers un buffer static ?)");
		if (alloc_size(r) < elen + 1)
			zft_failf(file, line, "bloc trop petit : %zu octet(s) pour une "
				"ligne de %zu caractère(s) + '\\0'", alloc_size(r), elen);
		free(r);
		g->pos = end;
		g->line++;
	}
	return (1);
}

void	gnl_expect(const char *file, int line, int fd, const char *data,
			size_t len, const char *what)
{
	t_gnl	g;

	gnl_init(&g, fd, data, len, what);
	while (gnl_step(file, line, &g))
		;
}
