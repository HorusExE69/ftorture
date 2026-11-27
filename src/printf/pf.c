/* ft_printf tester helpers: capture, comparison, fuzzing primitives.        */
#include <stdarg.h>
#include "pf.h"

int		(*volatile r_printf)(const char *fmt, ...) = printf;

t_cap	g_pf_ft;
t_cap	g_pf_rl;

int	pf_begin(int *saved)
{
	int	fd;

	fflush(stdout);
	fd = cap_open();
	*saved = dup(1);
	dup2(fd, 1);
	return (fd);
}

void	pf_end(int fd, int saved, t_cap *c)
{
	const char	*out;
	size_t		len;

	fflush(stdout);
	dup2(saved, 1);
	close(saved);
	out = cap_read(fd, &len);
	if (len > sizeof(c->buf))
		len = sizeof(c->buf);
	memcpy(c->buf, out, len);
	c->len = len;
	close(fd);
}

static void	show(char *dst, size_t dsz, const t_cap *c)
{
	char	esc[1100];

	zft_esc(esc, sizeof(esc), c->buf, c->len > 250 ? 250 : c->len);
	snprintf(dst, dsz, "\"%s%s\"  [retour %d]", esc, c->len > 250 ? "…" : "",
		c->ret);
}

void	pf_compare(const char *file, int line, const t_cap *ft,
			const t_cap *rl)
{
	char	exp[1300];
	char	got[1300];

	if (ft->ret == rl->ret && ft->len == rl->len
		&& memcmp(ft->buf, rl->buf, ft->len) == 0)
		return ;
	show(exp, sizeof(exp), rl);
	show(got, sizeof(got), ft);
	zft_fail(file, line, ft->ret != rl->ret && ft->len == rl->len
		&& memcmp(ft->buf, rl->buf, ft->len) == 0
		? "même sortie mais mauvaise valeur de retour"
		: "sortie différente de printf", exp, got);
}

#define ONE(name, type, fmtv) \
void	pf_one_##name(const char *file, int line, const char *fmt, type v) \
{ \
	char	in[300]; \
	snprintf(in, sizeof(in), fmtv, v); \
	INPUT("ft_printf(%s, %s)", zft_str(fmt), in); \
	PF_RUN(g_pf_ft, ft_printf(fmt, v)); \
	PF_RUN(g_pf_rl, r_printf(fmt, v)); \
	pf_compare(file, line, &g_pf_ft, &g_pf_rl); \
}

ONE(i, int, "%d")
ONE(u, unsigned, "%uU")
ONE(p, void *, "(void *)%p")
ONE(c, int, "%d")

void	pf_one_s(const char *file, int line, const char *fmt, const char *v)
{
	INPUT("ft_printf(%s, %s)", zft_str(fmt), zft_str(v));
	PF_RUN(g_pf_ft, ft_printf(fmt, v));
	PF_RUN(g_pf_rl, r_printf(fmt, v));
	pf_compare(file, line, &g_pf_ft, &g_pf_rl);
}

int	pf_rand_int(void)
{
	static const int	special[] = {0, 1, -1, 9, 10, -10, 42, -42, INT_MAX,
		INT_MIN, INT_MAX - 1, INT_MIN + 1, 100, -100, 1000000};

	if (zrand() % 4 == 0)
		return (special[zrand() % (sizeof(special) / sizeof(*special))]);
	return ((int)zrand() >> (zrand() % 31));
}

unsigned	pf_rand_uint(void)
{
	static const unsigned	special[] = {0, 1, 9, 10, 15, 16, 255, 256,
		0xdeadbeef, UINT_MAX, UINT_MAX - 1, 0x80000000u};

	if (zrand() % 4 == 0)
		return (special[zrand() % (sizeof(special) / sizeof(*special))]);
	return (zrand() >> (zrand() % 32));
}

void	*pf_rand_ptr(void)
{
	static const uintptr_t	special[] = {0, 1, 0xf, 0x10, 0xdeadbeef,
		UINTPTR_MAX, (uintptr_t)1 << 63, ((uintptr_t)1 << 63) - 1};

	if (zrand() % 3 == 0)
		return ((void *)special[zrand() % (sizeof(special) / sizeof(*special))]);
	return ((void *)(((uintptr_t)zrand() << 32 | zrand())
			>> (zrand() % 64)));
}

const char	*pf_rand_str(void)
{
	static char			buf[8][40];
	static int			k;
	static const char	*fixed[] = {"", "a", "Hello", "42 Lyon", "%d%s",
		"\t\n", "\xe9t\xe9", "a long-ish string with spaces"};
	char				*b;
	size_t				l;

	if (zrand() % 3 == 0)
		return (fixed[zrand() % (sizeof(fixed) / sizeof(*fixed))]);
	b = buf[k++ & 7];
	l = zrand() % 30;
	for (size_t i = 0; i < l; i++)
		b[i] = (char)(' ' + zrand() % 95);
	b[l] = 0;
	return (b);
}

static void	dirty_compare(const char *file, int line, const char *what)
{
	char	exp[1300];
	char	got[1300];

	if (g_pf_ft.ret == g_pf_rl.ret && g_pf_ft.len == g_pf_rl.len
		&& memcmp(g_pf_ft.buf, g_pf_rl.buf, g_pf_ft.len) == 0)
		return ;
	show(exp, sizeof(exp), &g_pf_rl);
	show(got, sizeof(got), &g_pf_ft);
	zft_fail(file, line, what, exp, got);
}

#define DIRTY_WHY "un int est lu avec va_arg(ap, int) / (unsigned int) : " \
	"les 32 bits hauts de son emplacement 64 bits ne sont pas définis " \
	"(ici non nuls, comme souvent à la moulinette)"

void	pf_dirty(const char *file, int line, const char *fmt, int v)
{
	INPUT("ft_printf(%s, %d) · 32 bits hauts de l'argument non nuls",
		zft_str(fmt), v);
	PF_RUN(g_pf_ft, ft_printf(fmt, DIRTY(v)));
	PF_RUN(g_pf_rl, r_printf(fmt, v));
	dirty_compare(file, line, DIRTY_WHY);
}

void	pf_dirty8(const char *file, int line, const char *fmt, const int *v)
{
	INPUT("ft_printf(%s, %d, %d, %d, %d, %d, %d, %d, %d) · 32 bits hauts "
		"non nuls (les derniers sur la pile)", zft_str(fmt), v[0], v[1], v[2],
		v[3], v[4], v[5], v[6], v[7]);
	PF_RUN(g_pf_ft, ft_printf(fmt, DIRTY(v[0]), DIRTY(v[1]), DIRTY(v[2]),
			DIRTY(v[3]), DIRTY(v[4]), DIRTY(v[5]), DIRTY(v[6]), DIRTY(v[7])));
	PF_RUN(g_pf_rl, r_printf(fmt, v[0], v[1], v[2], v[3], v[4], v[5], v[6],
			v[7]));
	dirty_compare(file, line, DIRTY_WHY);
}

void	pf_multi(const char *file, int line, const char *fmt, const long *a)
{
	INPUT("ft_printf(%s, …8 arguments)", zft_str(fmt));
	PF_RUN(g_pf_ft, ft_printf(fmt, a[0], a[1], a[2], a[3], a[4], a[5], a[6],
			a[7]));
	PF_RUN(g_pf_rl, r_printf(fmt, a[0], a[1], a[2], a[3], a[4], a[5], a[6],
			a[7]));
	pf_compare(file, line, &g_pf_ft, &g_pf_rl);
}
