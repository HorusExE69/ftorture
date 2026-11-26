/* ************************************************************************** */
/*  ftorture C test execution & benchmark shim (JSONL-only backend).          */
/*  Runs forked C tests with memtrack/VS/MTEST and nanosecond benchmarks,     */
/*  emitting structured JSONL events for Python to render and aggregate.      */
/* ************************************************************************** */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include "zft.h"
#include "project.h"

extern int		g_zm_active;
extern int		g_fail_at;
extern int		g_armed;
extern int		g_armed_count;
extern int		g_zm_bad_free;
extern char		g_zm_bad_msg[];
void			zm_reset(void);
int				zm_live_blocks(void);
size_t			zm_live_bytes(void);

int				g_ref;
volatile long	g_bench_sink;
t_cost			g_bench_cost;
double			g_score_ideal;
double			g_score_real;

#define g_funcs (g_proj.funcs)
#define NFUNCS (g_proj.nfuncs)
#define g_part_names (g_proj.part_names)

static struct s_opt
{
	int			spec;
	int			part;
	const char	*only;
	const char	*path;
	unsigned	seed;
	int			timeout;
	int			spec_pass;
	int			english;
	int			eff;
	int			eff_target;
	const char	*names;
}	o = {0, 0, NULL, ".", 42, 3, 0, 0, 0, 50, NULL};

#define L(fr, en) (o.english ? (en) : (fr))

static void	localize_project(void)
{
	int	i;

	if (!o.english)
		return ;
	if (!strcmp(g_proj.name, "libft"))
	{
		g_part_names[1] = "libc functions";
		g_part_names[2] = "Additional functions";
		g_part_names[3] = "Linked lists";
		g_proj.short_names[2] = "additional";
		g_proj.short_names[3] = "linked lists";
	}
	else if (!strcmp(g_proj.name, "ft_printf"))
	{
		g_part_names[1] = "Mandatory · cspdiuxX%";
		g_part_names[2] = "Bonus · - 0 . width # + space";
		g_proj.short_names[1] = "mandatory";
		for (i = 0; i < NFUNCS; i++)
		{
			if (!strcmp(g_funcs[i].name, "pf_width"))
				g_funcs[i].label = "width";
			else if (!strcmp(g_funcs[i].name, "pf_prec"))
				g_funcs[i].label = "precision .";
			else if (!strcmp(g_funcs[i].name, "pf_space"))
				g_funcs[i].label = "flag space";
			else if (!strcmp(g_funcs[i].name, "pf_mix"))
				g_funcs[i].label = "mixed";
			else if (!strcmp(g_funcs[i].name, "pf_combo"))
				g_funcs[i].label = "combinations";
			else if (!strcmp(g_funcs[i].name, "pf_edge"))
				g_funcs[i].label = "edge cases";
			else if (!strcmp(g_funcs[i].name, "pf_undef"))
				g_funcs[i].label = "undefined";
		}
	}
	else if (!strcmp(g_proj.name, "get_next_line"))
	{
		g_part_names[1] = "Mandatory · BUFFER_SIZE";
		g_part_names[2] = "Bonus · multi-fd";
		g_proj.short_names[1] = "mandatory";
		for (i = 0; i < NFUNCS; i++)
			if (!strcmp(g_funcs[i].name, "bsdef"))
				g_funcs[i].label = "no -D (default)";
	}
}

static double	safe_dbl(double v)
{
	return (isfinite(v) ? v : 0.0);
}

/* ============================================================ JSONL out == */
static void	json_str(const char *s)
{
	const unsigned char	*p = (const unsigned char *)(s ? s : "");

	putchar('"');
	while (*p)
	{
		if (*p == '"')
			fputs("\\\"", stdout);
		else if (*p == '\\')
			fputs("\\\\", stdout);
		else if (*p == '\n')
			fputs("\\n", stdout);
		else if (*p == '\r')
			fputs("\\r", stdout);
		else if (*p == '\t')
			fputs("\\t", stdout);
		else if (*p < 0x20)
			printf("\\u%04x", *p);
		else
			putchar(*p);
		p++;
	}
	putchar('"');
}

/* ============================================================ registry === */
static t_test	*g_tests;
static int		g_ntests;
static int		g_cap;

void	zft_register(const char *func, const char *name, t_kind kind, int spec,
			void (*fn)(void), const char *file, int line, int idx)
{
	t_test	*nt;

	if (g_ntests == g_cap)
	{
		g_cap = g_cap ? g_cap * 2 : 128;
		nt = realloc(g_tests, (size_t)g_cap * sizeof(*g_tests));
		if (!nt)
			abort();
		g_tests = nt;
	}
	int	seq = g_ntests++;

	g_tests[seq] = (t_test){func, name, kind, spec, fn, file, line,
		seq + 1, idx};
}

static int	func_index(const char *name)
{
	int	i;

	for (i = 0; i < NFUNCS; i++)
		if (!strcmp(g_funcs[i].name, name))
			return (i);
	return (NFUNCS);
}

static int	cmp_tests(const void *a, const void *b)
{
	const t_test	*x = a;
	const t_test	*y = b;
	int				ix = func_index(x->func);
	int				iy = func_index(y->func);

	if (ix != iy)
		return (ix - iy);
	return (x->seq - y->seq);
}

/* ======================================================== shared memory == */
typedef struct s_shm
{
	int		failed;
	int		done;
	int		soft;
	int		line;
	char	file[256];
	char	msg[512];
	char	expected[512];
	char	got[512];
	char	input[512];
	char	out[16384];
	size_t	outlen;
	int		leaks;
	size_t	leak_bytes;
	int		armed_count;
	int		bad_free;
	char	bad_msg[160];
}	t_shm;

static t_shm	*g_shm;

static void	copy_trunc(char *dst, size_t dsz, const char *src)
{
	size_t	n;

	if (!dsz)
		return ;
	if (!src)
	{
		dst[0] = 0;
		return ;
	}
	n = strlen(src);
	if (n >= dsz)
	{
		n = dsz - 1;
		while (n > 0 && (((unsigned char)src[n] & 0xC0) == 0x80))
			n--;
	}
	memcpy(dst, src, n);
	dst[n] = 0;
}

/* ============================================================ helpers ==== */
void	zft_esc(char *dst, size_t dsz, const char *s, size_t n)
{
	size_t	i;
	size_t	j = 0;

	if (!dsz)
		return ;
	for (i = 0; i < n && j + 8 < dsz; i++)
	{
		unsigned char	c = (unsigned char)s[i];
		int				w;

		if (c == '\n')
			w = snprintf(dst + j, dsz - j, "\\n");
		else if (c == '\r')
			w = snprintf(dst + j, dsz - j, "\\r");
		else if (c == '\t')
			w = snprintf(dst + j, dsz - j, "\\t");
		else if (c == '\0')
			w = snprintf(dst + j, dsz - j, "\\0");
		else if (c == '"' || c == '\\')
			w = snprintf(dst + j, dsz - j, "\\%c", c);
		else if (c >= 32 && c < 127)
			w = snprintf(dst + j, dsz - j, "%c", c);
		else
			w = snprintf(dst + j, dsz - j, "\\x%02x", c);
		if (w > 0 && j + (size_t)w < dsz)
			j += (size_t)w;
		else
			break ;
	}
	if (i < n && j + 4 < dsz)
		j += (size_t)snprintf(dst + j, dsz - j, "…");
	dst[j] = 0;
}

static char	*ring(void)
{
	static char	r[8][1100];
	static int	k;

	k = (k + 1) & 7;
	r[k][0] = 0;
	return (r[k]);
}

const char	*zft_str(const char *s)
{
	char	*b = ring();
	char	e[1024];
	size_t	l;

	if (!s)
		return ("NULL");
	l = strlen(s);
	zft_esc(e, sizeof(e), s, l > 300 ? 300 : l);
	snprintf(b, 1100, "\"%s\"%s", e, l > 300 ? "…" : "");
	return (b);
}

const char	*zft_mem(const void *p, size_t n)
{
	char				*b = ring();
	const unsigned char	*u = p;
	size_t				i;
	size_t				j = 0;
	size_t				lim = n > 24 ? 24 : n;

	if (!p)
		return ("NULL");
	b[0] = 0;
	for (i = 0; i < lim && j + 4 < 1100; i++)
		j += (size_t)snprintf(b + j, 1100 - j, "%s%02x", i ? " " : "", u[i]);
	if (n > lim && j + 16 < 1100)
		snprintf(b + j, 1100 - j, " …(%zuB)", n);
	return (b);
}

void	zft_fail(const char *file, int line, const char *expr,
			const char *expected, const char *got)
{
	g_shm->failed = 1;
	g_shm->line = line;
	copy_trunc(g_shm->file, sizeof(g_shm->file), file);
	snprintf(g_shm->msg, sizeof(g_shm->msg), "%s", expr ? expr : "check");
	copy_trunc(g_shm->expected, sizeof(g_shm->expected), expected);
	copy_trunc(g_shm->got, sizeof(g_shm->got), got);
	_exit(1);
}

void	zft_failf(const char *file, int line, const char *fmt, ...)
{
	va_list	ap;

	g_shm->failed = 1;
	g_shm->line = line;
	copy_trunc(g_shm->file, sizeof(g_shm->file), file);
	va_start(ap, fmt);
	vsnprintf(g_shm->msg, sizeof(g_shm->msg), fmt, ap);
	va_end(ap);
	_exit(1);
}

void	zft_out(const char *fmt, ...)
{
	va_list	ap;
	int		w;

	if (g_shm->outlen + 2 >= sizeof(g_shm->out))
		return ;
	if (g_shm->outlen)
		g_shm->out[g_shm->outlen++] = '|';
	va_start(ap, fmt);
	w = vsnprintf(g_shm->out + g_shm->outlen,
			sizeof(g_shm->out) - g_shm->outlen, fmt, ap);
	va_end(ap);
	if (w > 0)
	{
		size_t	rem = sizeof(g_shm->out) - g_shm->outlen - 1;

		g_shm->outlen += (size_t)w < rem ? (size_t)w : rem;
	}
}

void	zft_input(const char *fmt, ...)
{
	va_list	ap;

	va_start(ap, fmt);
	vsnprintf(g_shm->input, sizeof(g_shm->input), fmt, ap);
	va_end(ap);
}

const char	*zft_path(void) { return (o.path); }
void		zft_soft(void) { g_shm->soft = 1; }
int			zft_en(void) { return (o.english); }

/* ======================================================== child runner === */
typedef struct s_run
{
	int		sig;
	int		code;
	t_shm	s;
}	t_run;

static void	run_child(const t_test *t, int ref, int fail_at, t_run *out)
{
	pid_t	pid;
	int		st = 0;

	memset(g_shm, 0, sizeof(*g_shm));
	fflush(stdout);
	pid = fork();
	if (pid < 0)
	{
		memset(out, 0, sizeof(*out));
		out->sig = SIGABRT;
		return ;
	}
	if (pid == 0)
	{
		int	dn = open("/dev/null", O_RDWR);

		if (dn >= 0)
		{
			dup2(dn, 0);
			dup2(dn, 1);
			dup2(dn, 2);
			if (dn > 2)
				close(dn);
		}
		signal(SIGPIPE, SIG_IGN);
		alarm((unsigned)o.timeout);
		zsrand(o.seed);
		g_ref = ref;
		g_fail_at = fail_at;
		g_armed = 0;
		zm_reset();
		g_zm_active = !ref;
		t->fn();
		g_zm_active = 0;
		g_shm->leaks = zm_live_blocks();
		g_shm->leak_bytes = zm_live_bytes();
		g_shm->armed_count = g_armed_count;
		g_shm->bad_free = g_zm_bad_free;
		if (g_zm_bad_free)
			copy_trunc(g_shm->bad_msg, sizeof(g_shm->bad_msg), g_zm_bad_msg);
		g_shm->done = 1;
		_exit(0);
	}
	while (waitpid(pid, &st, 0) < 0 && errno == EINTR)
		;
	out->sig = WIFSIGNALED(st) ? WTERMSIG(st) : 0;
	out->code = WIFEXITED(st) ? WEXITSTATUS(st) : 0;
	out->s = *g_shm;
}

/* ======================================================== evaluation ===== */
enum { R_PASS = 0, R_PASS_CRASH = 1, R_FAIL = 2, R_SPEC = 3 };

typedef struct s_result
{
	int			res;
	const char	*glyph;
	const char	*why;
	int			sig;
	int			fail_at;
	int			line;
	char		file[256];
	char		msg[512];
	char		input[512];
	char		expected[512];
	char		actual[512];
}	t_result;

static void	set_fail(t_result *r, int res, const char *glyph, const char *why,
				const t_shm *s, int sig, int fail_at)
{
	r->res = res;
	r->glyph = glyph;
	r->why = why;
	r->sig = sig;
	r->fail_at = fail_at;
	r->line = s ? s->line : 0;
	copy_trunc(r->file, sizeof(r->file), s ? s->file : "");
	copy_trunc(r->msg, sizeof(r->msg), s ? s->msg : "");
	copy_trunc(r->input, sizeof(r->input), s ? s->input : "");
	copy_trunc(r->expected, sizeof(r->expected), s ? s->expected : "");
	copy_trunc(r->actual, sizeof(r->actual), s ? s->got : "");
}

static void	eval_normal(const t_test *t, t_result *r)
{
	t_run	a;

	memset(r, 0, sizeof(*r));
	run_child(t, 0, 0, &a);
	if (a.sig)
	{
		int	spec = t->spec;

		set_fail(r, spec ? R_SPEC : R_FAIL, a.sig == SIGALRM ? "T" : "S",
			"sig", &a.s, a.sig, 0);
		snprintf(r->msg, sizeof(r->msg), a.sig == SIGALRM
			? L("timeout (%ds)", "timeout (%ds)")
			: L("crash (signal %d)", "crash (signal %d)"),
			a.sig == SIGALRM ? o.timeout : a.sig);
		return ;
	}
	if (a.s.failed)
	{
		int	spec = t->spec || a.s.soft;

		set_fail(r, spec ? R_SPEC : R_FAIL, spec ? "▲" : "✘", "assert",
			&a.s, 0, 0);
		return ;
	}
	if (!a.s.done)
	{
		set_fail(r, t->spec ? R_SPEC : R_FAIL, "✘", "exit", &a.s, 0, 0);
		snprintf(r->msg, sizeof(r->msg), L("a appelé exit(%d)", "called exit(%d)"),
			a.code);
		return ;
	}
	if (a.s.bad_free)
	{
		set_fail(r, t->spec ? R_SPEC : R_FAIL, "✘", "assert", &a.s, 0, 0);
		copy_trunc(r->msg, sizeof(r->msg), a.s.bad_msg);
		return ;
	}
	if (a.s.leaks)
	{
		set_fail(r, t->spec ? R_SPEC : R_FAIL, "L", "leak", &a.s, 0, 0);
		snprintf(r->msg, sizeof(r->msg),
			L("fuite mémoire : %d bloc(s), %zu octet(s)",
				"memory leak: %d block(s), %zu byte(s)"),
			a.s.leaks, a.s.leak_bytes);
		return ;
	}
	r->res = R_PASS;
	r->glyph = "✔";
}

static void	eval_vs(const t_test *t, t_result *r)
{
	t_run	a;
	t_run	b;
	int		fc;
	int		rc;

	memset(r, 0, sizeof(*r));
	run_child(t, 0, 0, &a);
	run_child(t, 1, 0, &b);
	if (a.sig == SIGALRM)
	{
		set_fail(r, R_FAIL, "T", "vs_timeout", &a.s, SIGALRM, 0);
		snprintf(r->msg, sizeof(r->msg), "timeout (%ds)", o.timeout);
		return ;
	}
	fc = a.sig != 0;
	rc = b.sig != 0 && b.sig != SIGALRM;
	if (fc && rc)
	{
		r->res = R_PASS_CRASH;
		r->glyph = "✔";
		return ;
	}
	if (fc && !rc)
	{
		set_fail(r, R_FAIL, "S", "vs_crash", &a.s, a.sig, 0);
		snprintf(r->msg, sizeof(r->msg),
			L("crash (signal %d) alors que l'original réussit",
				"crash (signal %d) while the original succeeds"), a.sig);
		copy_trunc(r->expected, sizeof(r->expected), b.s.out);
		return ;
	}
	if (!fc && rc)
	{
		set_fail(r, R_SPEC, "▲", "vs_spec", &a.s, 0, 0);
		snprintf(r->msg, sizeof(r->msg),
			L("l'original crash (signal %d), pas ta fonction",
				"the original crashes (signal %d), yours does not"), b.sig);
		copy_trunc(r->actual, sizeof(r->actual), a.s.out);
		return ;
	}
	if (a.s.failed)
	{
		set_fail(r, t->spec ? R_SPEC : R_FAIL, t->spec ? "▲" : "✘", "assert",
			&a.s, 0, 0);
		return ;
	}
	if (!a.s.done)
	{
		set_fail(r, R_FAIL, "✘", "exit", &a.s, 0, 0);
		snprintf(r->msg, sizeof(r->msg), L("a appelé exit(%d)", "called exit(%d)"),
			a.code);
		return ;
	}
	if (a.s.outlen != b.s.outlen || memcmp(a.s.out, b.s.out, a.s.outlen))
	{
		set_fail(r, t->spec ? R_SPEC : R_FAIL, t->spec ? "▲" : "✘",
			t->spec ? "vs_diff_spec" : "vs_diff", &a.s, 0, 0);
		copy_trunc(r->expected, sizeof(r->expected), b.s.out);
		copy_trunc(r->actual, sizeof(r->actual), a.s.out);
		return ;
	}
	if (a.s.bad_free)
	{
		set_fail(r, t->spec ? R_SPEC : R_FAIL, "✘", "assert", &a.s, 0, 0);
		copy_trunc(r->msg, sizeof(r->msg), a.s.bad_msg);
		return ;
	}
	if (a.s.leaks)
	{
		set_fail(r, R_FAIL, "L", "leak", &a.s, 0, 0);
		snprintf(r->msg, sizeof(r->msg),
			L("fuite mémoire : %d bloc(s), %zu octet(s)",
				"memory leak: %d block(s), %zu byte(s)"),
			a.s.leaks, a.s.leak_bytes);
		return ;
	}
	r->res = R_PASS;
	r->glyph = "✔";
}

static void	eval_malloc(const t_test *t, t_result *r)
{
	t_run	a;
	int		k;

	memset(r, 0, sizeof(*r));
	run_child(t, 0, 0, &a);
	if (a.sig || a.s.failed || !a.s.done || a.s.leaks)
	{
		eval_normal(t, r);
		return ;
	}
	for (k = 1; k <= a.s.armed_count && k <= 400; k++)
	{
		t_run	m;

		run_child(t, 0, k, &m);
		if (m.sig)
		{
			set_fail(r, R_FAIL, m.sig == SIGALRM ? "T" : "M", "malloc",
				&m.s, m.sig, k);
			snprintf(r->msg, sizeof(r->msg),
				L("échec malloc #%d : crash (signal %d)",
					"malloc #%d fails: crash (signal %d)"), k, m.sig);
			return ;
		}
		if (m.s.failed)
		{
			set_fail(r, R_FAIL, "M", "malloc", &m.s, 0, k);
			snprintf(r->msg, sizeof(r->msg),
				L("échec malloc #%d : %s", "malloc #%d fails: %s"), k, m.s.msg);
			return ;
		}
		if (!m.s.done)
		{
			set_fail(r, R_FAIL, "M", "malloc", &m.s, 0, k);
			snprintf(r->msg, sizeof(r->msg),
				L("échec malloc #%d : a appelé exit(%d)",
					"malloc #%d fails: called exit(%d)"), k, m.code);
			return ;
		}
		if (m.s.bad_free)
		{
			set_fail(r, R_FAIL, "M", "malloc", &m.s, 0, k);
			snprintf(r->msg, sizeof(r->msg),
				L("échec malloc #%d : %s", "malloc #%d fails: %s"), k, m.s.bad_msg);
			return ;
		}
		if (m.s.leaks)
		{
			set_fail(r, R_FAIL, "M", "malloc", &m.s, 0, k);
			snprintf(r->msg, sizeof(r->msg),
				L("échec malloc #%d : fuite de %d bloc(s) (%zu octet(s))",
					"malloc #%d fails: leak of %d block(s) (%zu byte(s))"),
				k, m.s.leaks, m.s.leak_bytes);
			return ;
		}
	}
	r->res = R_PASS;
	r->glyph = "✔";
}

/* ======================================================== benchmarks ===== */
typedef struct s_bench
{
	const char	*func;
	void		(*fn)(long);
	void		(*score)(void);
}	t_bench;

typedef struct s_bres
{
	char	label[64];
	int		pct;
	int		bound;
	double	ideal;
	double	real;
	int		score;
}	t_bres;

typedef struct s_bshm
{
	double	tft;
	double	ft_start;
	long	n;
	t_cost	cost;
	double	ideal;
}	t_bshm;

#define BENCH_MAX 64
#define BENCH_CALIB 0.015
#define BENCH_LIMIT 2.0

static t_bench	g_benches[BENCH_MAX];
static int		g_nbench;
static t_bres	g_br[BENCH_MAX];
static int		g_nbr;
static t_bshm	*g_bshm;
static t_cost	g_hw;
static int		g_hw_ok;

void	zft_bench_register(const char *func, void (*fn)(long),
			const char *file, int line)
{
	(void)file;
	(void)line;
	if (g_nbench < BENCH_MAX)
		g_benches[g_nbench++] = (t_bench){func, fn, NULL};
}

void	zft_score_register(const char *func, void (*fn)(void),
			const char *file, int line)
{
	(void)file;
	(void)line;
	if (g_nbench < BENCH_MAX)
		g_benches[g_nbench++] = (t_bench){func, NULL, fn};
}

static double	bnow(void)
{
	struct timespec	t;

	clock_gettime(CLOCK_MONOTONIC, &t);
	return ((double)t.tv_sec + (double)t.tv_nsec * 1e-9);
}

typedef struct s_hnode
{
	struct s_hnode	*next;
	void			*content;
}	t_hnode;

static int	hw_id(int c) { return (c); }
static int	hw_range(int c) { return (c >= 'a' && c <= 'z'); }

static int	(*volatile g_hw_fid)(int) = hw_id;
static int	(*volatile g_hw_frange)(int) = hw_range;

#define HW_N 4096
#define HW_RN 65536
#define HW_NODES 1024

#define HW_BEST(dst, units, body) do { double zq_b = 1e9; int zq_k; \
	for (zq_k = 0; zq_k < 20; zq_k++) { double zq_t = bnow(); body; \
	zq_t = bnow() - zq_t; if (zq_t < zq_b) zq_b = zq_t; } \
	(dst) = zq_b / (double)(units); } while (0)

static void	hw_calibrate(void)
{
	static char		a[HW_RN + 1];
	static char		b[HW_N + 1];
	static char		d[HW_RN + 1];
	static t_hnode	nodes[HW_NODES];
	char			path[] = "/tmp/ftorture_hwXXXXXX";
	int				dn = open("/dev/null", O_WRONLY);
	int				fd;
	volatile long	k = 0;
	long			i;
	double			range;

	if (g_hw_ok)
		return ;
	memset(a, 'a', HW_RN);
	a[HW_N] = 0;
	memset(b, 'a', HW_N);
	for (i = 0; i < HW_NODES; i++)
		nodes[i].next = i + 1 < HW_NODES ? &nodes[i + 1] : NULL;
	{
		const char	*pa = a;
		const char	*pb = b;
		char		*pd = d;
		int			(*fid)(int) = g_hw_fid;
		int			(*frange)(int) = g_hw_frange;
		double		v1;
		double		v2;

		HW_BEST(v1, HW_N, { size_t j = 0; while (pa[j]) j++; k = (long)j; });
		HW_BEST(v2, HW_N, { const char *q = pa; while (*q) q++; k = q - pa; });
		g_hw.scan = v1 < v2 ? v1 : v2;
		HW_BEST(v1, HW_N, { int j = 0; while (pa[j] != '#' && pa[j]) j++; k = j; });
		if (v1 < g_hw.scan)
			g_hw.scan = v1;
		HW_BEST(v1, HW_N, { size_t j = 0; while (pa[j]) { pd[j] = pa[j]; j++; } });
		HW_BEST(v2, HW_N, { const char *q = pa; char *w = pd; while (*q) *w++ = *q++; });
		g_hw.copy = v1 < v2 ? v1 : v2;
		HW_BEST(v1, HW_N, { int j = 0; while (pa[j]) { pd[j] = pa[j]; j++; } });
		if (v1 < g_hw.copy)
			g_hw.copy = v1;
		HW_BEST(v1, HW_N, { size_t j = 0; while (j < HW_N) pd[j++] = 'x'; });
		HW_BEST(v2, HW_N, { char *w = pd; size_t m = HW_N; while (m--) *w++ = 'x'; });
		g_hw.store = v1 < v2 ? v1 : v2;
		HW_BEST(v1, HW_N, { int j = 0; while (j < HW_N) { pd[j] = 'x'; j++; } });
		if (v1 < g_hw.store)
			g_hw.store = v1;
		HW_BEST(v1, HW_N, { size_t j = 0; while (pa[j] && pa[j] == pb[j]) j++; k = (long)j; });
		HW_BEST(v2, HW_N, { const char *x = pa; const char *y = pb; while (*x && *x == *y) { x++; y++; } k = x - pa; });
		g_hw.cmp = v1 < v2 ? v1 : v2;
		HW_BEST(v1, HW_N, { int j = 0; while (pa[j] && pa[j] == pb[j]) j++; k = j; });
		if (v1 < g_hw.cmp)
			g_hw.cmp = v1;
		HW_BEST(g_hw.iters, HW_N, { long sum = 0; int j; for (j = 0; j < HW_N; j++) sum += j; k = sum; });
		HW_BEST(v1, HW_N, { long sum = 0; int j; for (j = 0; j < HW_N; j++) sum += fid(j); k = sum; });
		HW_BEST(range, HW_N, { long sum = 0; int j; for (j = 0; j < HW_N; j++) sum += frange(j); k = sum; });
		g_hw.ops = (range - v1) / 2;
		g_hw.calls = v1 - g_hw.iters;
	}
	if (g_hw.calls < g_hw.iters / 4)
		g_hw.calls = g_hw.iters / 4;
	if (g_hw.ops < g_hw.iters / 20)
		g_hw.ops = g_hw.iters / 20;
	HW_BEST(g_hw.digits, 8192 * 10, for (i = 0; i < 8192; i++) {
		long v = 1000000000L + i; int j = 0;
		while (v) { d[j++] = (char)('0' + v % 10); v /= 10; } });
	HW_BEST(g_hw.nodes, HW_NODES * 16, for (i = 0; i < 16; i++) {
		t_hnode *l = nodes; long c = 0; while (l) { c++; l = l->next; } k = c; });
	HW_BEST(g_hw.allocs, 4096, for (i = 0; i < 4096; i++) {
		void *p = malloc(64); k += (long)(p != NULL); free(p); });
	HW_BEST(g_hw.big_allocs, 64, for (i = 0; i < 64; i++) {
		void *p = malloc(10 << 20); k += (long)(p != NULL); free(p); });
	if (dn >= 0)
		HW_BEST(g_hw.sys, 2048, for (i = 0; i < 2048; i++) k += write(dn, a, 1));
	fd = mkstemp(path);
	if (fd >= 0)
	{
		double	big;

		unlink(path);
		memset(a, 'a', HW_RN);
		k += write(fd, a, HW_RN);
		HW_BEST(big, 64, for (i = 0; i < 64; i++) k += pread(fd, d, HW_RN, 0));
		g_hw.rbytes = (big - g_hw.sys) / HW_RN;
		if (g_hw.rbytes < 0)
			g_hw.rbytes = 0;
		close(fd);
	}
	if (dn >= 0)
		close(dn);
	g_hw_ok = 1;
}

static double	ideal_time(const t_cost *c)
{
	return (c->iters * g_hw.iters + c->calls * g_hw.calls + c->ops * g_hw.ops
		+ c->scan * g_hw.scan + c->copy * g_hw.copy + c->store * g_hw.store
		+ c->cmp * g_hw.cmp + c->digits * g_hw.digits + c->nodes * g_hw.nodes
		+ c->allocs * g_hw.allocs + c->big_allocs * g_hw.big_allocs
		+ c->sys * g_hw.sys + c->rbytes * g_hw.rbytes);
}

static double	bench_once(void (*fn)(long), long n)
{
	double	t;

	g_ref = 0;
	g_bshm->ft_start = bnow();
	t = bnow();
	fn(n);
	t = bnow() - t;
	g_bshm->ft_start = 0;
	return (t);
}

static const t_bench	*bench_for(const char *func)
{
	int	i;

	for (i = 0; i < g_nbench; i++)
		if (!strcmp(g_benches[i].func, func))
			return (&g_benches[i]);
	return (NULL);
}

static t_bres	*run_bench(const t_bench *b, const char *label)
{
	t_bres	*r;
	pid_t	pid;
	int		st;
	double	start;
	double	ideal;

	if (g_nbr >= BENCH_MAX)
		return (NULL);
	r = &g_br[g_nbr++];
	memset(r, 0, sizeof(*r));
	copy_trunc(r->label, sizeof(r->label), label);
	r->pct = -1;
	r->score = b->score != NULL;
	if (!b->score)
		hw_calibrate();
	if (!g_bshm)
		g_bshm = mmap(NULL, sizeof(t_bshm), PROT_READ | PROT_WRITE,
				MAP_SHARED | MAP_ANONYMOUS, -1, 0);
	if (g_bshm == MAP_FAILED)
		return (g_bshm = NULL, r);
	memset(g_bshm, 0, sizeof(*g_bshm));
	fflush(stdout);
	pid = fork();
	if (pid < 0)
		return (r);
	if (pid == 0)
	{
		int		dn = open("/dev/null", O_RDWR);
		long	n = 1;
		double	t;
		int		k;

		if (dn >= 0)
		{
			dup2(dn, 0);
			dup2(dn, 1);
			dup2(dn, 2);
			if (dn > 2)
				close(dn);
		}
		signal(SIGPIPE, SIG_IGN);
		g_zm_active = 0;
		g_fail_at = 0;
		g_armed = 0;
		zsrand(o.seed);
		if (b->score)
		{
			g_score_ideal = 0;
			g_score_real = 0;
			b->score();
			g_bshm->ideal = g_score_ideal;
			g_bshm->tft = g_score_real;
			g_bshm->n = 1;
			_exit(0);
		}
		memset(&g_bench_cost, 0, sizeof(g_bench_cost));
		t = bench_once(b->fn, 1);
		g_bshm->cost = g_bench_cost;
		g_bshm->tft = t;
		while ((t = bench_once(b->fn, n)) < BENCH_CALIB && n < (1L << 30))
		{
			g_bshm->tft = t / (double)n;
			n = t > BENCH_CALIB / 64 ? (long)((double)n * BENCH_CALIB / t) + 1
				: n * 4;
		}
		g_bshm->tft = t / (double)n;
		g_bshm->n = n;
		for (k = 1; k < 3; k++)
			if ((t = bench_once(b->fn, n) / (double)n) < g_bshm->tft)
				g_bshm->tft = t;
		_exit(0);
	}
	start = bnow();
	while (1)
	{
		pid_t	w = waitpid(pid, &st, WNOHANG);
		double	fs = g_bshm->ft_start;

		if (w == pid || (w < 0 && errno != EINTR))
			break ;
		if ((!b->score && fs > 0 && bnow() - fs > BENCH_LIMIT)
			|| bnow() - start > (b->score ? 120.0 : 30.0))
		{
			kill(pid, SIGKILL);
			while (waitpid(pid, &st, 0) < 0 && errno == EINTR)
				;
			if (!g_bshm->n && fs > 0)
			{
				g_bshm->tft = bnow() - fs;
				r->bound = 1;
			}
			st = 0;
			break ;
		}
		usleep(2000);
	}
	ideal = b->score ? g_bshm->ideal : ideal_time(&g_bshm->cost);
	r->ideal = ideal;
	r->real = g_bshm->tft;
	if ((r->bound || (WIFEXITED(st) && !WEXITSTATUS(st)))
		&& ideal > 0 && g_bshm->tft > 0)
	{
		double	p = ideal / g_bshm->tft * 100.0;

		r->pct = p > 9999 ? 9999 : p < 1 ? 1 : (int)(p + 0.5);
	}
	return (r);
}

static void	json_eff(const t_bres *r)
{
	if (!r || r->pct < 0)
	{
		fputs("null", stdout);
		return ;
	}
	fputs("{\"label\":", stdout);
	json_str(r->label);
	printf(",\"pct\":%d,\"ideal\":%.9g,\"real\":%.9g,\"bound\":%s,\"score\":%s}",
		r->pct, safe_dbl(r->ideal), safe_dbl(r->real), r->bound ? "true" : "false",
		r->score ? "true" : "false");
}

/* ======================================================== selection ====== */
static int	selected(const t_func *f)
{
	const char	*p;

	if (o.part && f->part != o.part)
		return (0);
	if (!o.only)
		return (1);
	p = o.only;
	while (*p)
	{
		size_t	l = strcspn(p, ",");
		char	w[64];

		snprintf(w, sizeof(w), "%.*s", (int)(l < 63 ? l : 63), p);
		if (!strcmp(w, f->name)
			|| (!strncmp(f->name, "ft_", 3) && !strcmp(w, f->name + 3))
			|| (f->label && !strcmp(w, f->label)))
			return (1);
		p += l + (p[l] == ',');
	}
	return (0);
}

static int	g_any_bad;

static void	run_function(int fi, int *ti)
{
	t_func		*f = &g_funcs[fi];
	int			start = *ti;
	int			end = start;
	int			i;
	int			pass = 0;
	int			fail = 0;
	int			spec = 0;
	int			crash_eq = 0;
	const char	*lbl = f->label ? f->label : f->name;

	while (end < g_ntests && !strcmp(g_tests[end].func, f->name))
		end++;
	*ti = end;
	if (!selected(f))
		return ;
	fputs("{\"type\":\"suite_start\",\"key\":", stdout);
	json_str(f->name);
	fputs(",\"label\":", stdout);
	json_str(lbl);
	printf(",\"part\":%d,\"short\":", f->part);
	json_str(g_proj.short_names[f->part]);
	printf(",\"missing\":%s,\"archive\":", !f->addr ? "true" : "false");
	json_str(g_proj.archive);
	printf(",\"total\":%d}\n", end - start);
	fflush(stdout);
	if (!f->addr)
	{
		g_any_bad = 1;
		return ;
	}
	for (i = start; i < end; i++)
	{
		t_result	r;

		if (g_tests[i].kind == K_VSREF)
			eval_vs(&g_tests[i], &r);
		else if (g_tests[i].kind == K_MALLOC)
			eval_malloc(&g_tests[i], &r);
		else
			eval_normal(&g_tests[i], &r);
		if (o.spec_pass && r.res == R_FAIL)
			r.res = R_SPEC;
		if (r.res == R_PASS)
			pass++;
		else if (r.res == R_PASS_CRASH)
		{
			pass++;
			crash_eq++;
		}
		else if (r.res == R_SPEC)
			spec++;
		else if (r.res == R_FAIL)
			fail++;
		printf("{\"type\":\"test\",\"index\":%d,\"res\":%d,\"glyph\":",
			i - start + 1, r.res);
		json_str(r.glyph);
		if (r.res == R_FAIL || r.res == R_SPEC)
		{
			fputs(",\"name\":", stdout);
			json_str(g_tests[i].name);
			fputs(",\"file\":", stdout);
			json_str(r.file[0] ? r.file : g_tests[i].file);
			printf(",\"line\":%d,\"test_line\":%d,\"tidx\":%d,\"suite\":",
				r.line ? r.line : g_tests[i].line, g_tests[i].line,
				g_tests[i].idx);
			json_str(f->name);
			printf(",\"why\":");
			json_str(r.why);
			printf(",\"sig\":%d,\"fail_at\":%d", r.sig, r.fail_at);
			#ifdef Z_BS
			printf(",\"z_bs\":%d", (int)(Z_BS));
			#endif
			fputs(",\"msg\":", stdout);
			json_str(r.msg);
			fputs(",\"input\":", stdout);
			json_str(r.input);
			fputs(",\"expected\":", stdout);
			json_str(r.expected);
			fputs(",\"actual\":", stdout);
			json_str(r.actual);
		}
		fputs("}\n", stdout);
		fflush(stdout);
	}
	if (fail || (o.spec && spec))
		g_any_bad = 1;
	{
		t_bres	*br = NULL;

		if (o.eff && bench_for(f->name))
		{
			char	bl[64];
			int		k;
			int		dup = 0;

			for (k = 0; k < NFUNCS; k++)
				if (k != fi && g_funcs[k].part != f->part && f->label
					&& g_funcs[k].label && !strcmp(g_funcs[k].label, f->label))
					dup = 1;
			snprintf(bl, sizeof(bl), "%s%s", lbl,
				dup && f->part == 2 ? " (bonus)" : "");
			br = run_bench(bench_for(f->name), bl);
		}
		fputs("{\"type\":\"suite_end\",\"key\":", stdout);
		json_str(f->name);
		fputs(",\"label\":", stdout);
		json_str(lbl);
		printf(",\"part\":%d,\"pass\":%d,\"fail\":%d,\"spec\":%d,"
			"\"crash_eq\":%d,\"total\":%d,\"missing\":false,\"eff\":",
			f->part, pass, fail, spec, crash_eq, end - start);
		json_eff(br);
		fputs("}\n", stdout);
		fflush(stdout);
	}
}

static void	run_project_benches(void)
{
	int		i;
	int		j;
	char	lbl[64];

	if (!o.eff)
		return ;
	for (i = 0; i < g_nbench; i++)
	{
		t_bres	*r;

		for (j = 0; j < NFUNCS; j++)
			if (!strcmp(g_funcs[j].name, g_benches[i].func))
				break ;
		if (j < NFUNCS)
			continue ;
		snprintf(lbl, sizeof(lbl), "%s%s", g_benches[i].func,
			o.part == 2 ? " (bonus)" : "");
		r = run_bench(&g_benches[i], lbl);
		if (r && r->pct >= 0)
		{
			fputs("{\"type\":\"bench\",\"label\":", stdout);
			json_str(r->label);
			printf(",\"pct\":%d,\"ideal\":%.9g,\"real\":%.9g,\"bound\":%s,\"score\":%s}\n",
				r->pct, safe_dbl(r->ideal), safe_dbl(r->real), r->bound ? "true" : "false",
				r->score ? "true" : "false");
			fflush(stdout);
		}
	}
}

int	main(int ac, char **av)
{
	int			i;
	int			ti;
	int			part;
	const char	*locale;

	locale = getenv("LC_ALL");
	if (!locale || !*locale)
		locale = getenv("LC_MESSAGES");
	if (!locale || !*locale)
		locale = getenv("LANG");
	o.english = (!locale || strncmp(locale, "fr", 2));
	for (i = 1; i < ac; i++)
	{
		const char	*a = av[i];

		if (!strcmp(a, "-s") || !strcmp(a, "--speculative"))
			o.spec = 1;
		else if ((!strcmp(a, "-f") || !strcmp(a, "--func")) && i + 1 < ac)
			o.only = av[++i];
		else if ((!strcmp(a, "-p") || !strcmp(a, "--part")) && i + 1 < ac)
			o.part = atoi(av[++i]);
		else if (!strcmp(a, "--path") && i + 1 < ac)
			o.path = av[++i];
		else if (!strcmp(a, "--seed") && i + 1 < ac)
			o.seed = (unsigned)strtoul(av[++i], NULL, 10);
		else if (!strcmp(a, "--timeout") && i + 1 < ac)
			o.timeout = atoi(av[++i]);
		else if (!strcmp(a, "-e") || !strcmp(a, "--efficiency"))
		{
			o.eff = 1;
			if (i + 1 < ac && av[i + 1][0] >= '0' && av[i + 1][0] <= '9')
				o.eff_target = atoi(av[++i]);
		}
		else if ((!strcmp(a, "-t") || !strcmp(a, "--target")) && i + 1 < ac)
		{
			o.eff = 1;
			o.eff_target = atoi(av[++i]);
		}
		else if (!strcmp(a, "--lang") && i + 1 < ac)
			o.english = !strcmp(av[++i], "en");
		else if (!strcmp(a, "--spec-pass"))
			o.spec_pass = 1;
		else if (!strcmp(a, "--name") && i + 1 < ac)
			o.names = av[++i];
		else if (!strcmp(a, "-v") || !strcmp(a, "--verbose")
			|| !strcmp(a, "--no-color") || !strcmp(a, "--no-banner")
			|| !strcmp(a, "--json"))
			;
		else if ((!strcmp(a, "--log") || !strcmp(a, "--repro-cmd")
				|| !strcmp(a, "--checks")) && i + 1 < ac)
			i++;
		else
			return (2);
	}
	if (o.timeout < 1)
		o.timeout = 3;
	localize_project();
	g_shm = mmap(NULL, sizeof(t_shm), PROT_READ | PROT_WRITE,
			MAP_SHARED | MAP_ANONYMOUS, -1, 0);
	if (g_shm == MAP_FAILED)
		return (perror("mmap"), 2);
	if (o.names)
	{
		int	k = 0;

		for (i = 0; i < g_ntests; i++)
		{
			const char	*p = o.names;
			int			keep = 0;

			while (*p && !keep)
			{
				size_t	l = strcspn(p, ",");
				char	w[256];

				snprintf(w, sizeof(w), "%.*s", (int)(l < 255 ? l : 255), p);
				keep = l && strstr(g_tests[i].name, w) != NULL;
				p += l + (p[l] == ',');
			}
			if (keep)
				g_tests[k++] = g_tests[i];
		}
		g_ntests = k;
	}
	qsort(g_tests, (size_t)g_ntests, sizeof(t_test), cmp_tests);
	ti = 0;
	part = 0;
	for (i = 0; i < NFUNCS; i++)
	{
		if (g_funcs[i].part != part && (!o.part || o.part == g_funcs[i].part))
		{
			int		j;
			int		any = 0;
			char	title[128];

			for (j = i; j < NFUNCS && g_funcs[j].part == g_funcs[i].part; j++)
				any |= selected(&g_funcs[j]);
			part = g_funcs[i].part;
			if (any)
			{
				snprintf(title, sizeof(title), "%s %d · %s", L("PARTIE", "PART"),
					part, g_part_names[part]);
				printf("{\"type\":\"part\",\"part\":%d,\"title\":", part);
				json_str(title);
				fputs(",\"short\":", stdout);
				json_str(g_proj.short_names[part]);
				fputs("}\n", stdout);
				fflush(stdout);
			}
		}
		while (ti < g_ntests && func_index(g_tests[ti].func) < i)
			ti++;
		run_function(i, &ti);
	}
	run_project_benches();
	if (g_hw_ok)
	{
		printf("{\"type\":\"hw\",\"iters\":%.9g,\"scan\":%.9g,\"copy\":%.9g,"
			"\"store\":%.9g,\"cmp\":%.9g,\"calls\":%.9g,\"ops\":%.9g,"
			"\"digits\":%.9g,\"nodes\":%.9g,\"allocs\":%.9g,"
			"\"big_allocs\":%.9g,\"sys\":%.9g,\"rbytes\":%.9g}\n",
			safe_dbl(g_hw.iters), safe_dbl(g_hw.scan), safe_dbl(g_hw.copy),
			safe_dbl(g_hw.store), safe_dbl(g_hw.cmp), safe_dbl(g_hw.calls),
			safe_dbl(g_hw.ops), safe_dbl(g_hw.digits), safe_dbl(g_hw.nodes),
			safe_dbl(g_hw.allocs), safe_dbl(g_hw.big_allocs),
			safe_dbl(g_hw.sys), safe_dbl(g_hw.rbytes));
		fflush(stdout);
	}
	return (g_any_bad ? 1 : 0);
}
