/* ************************************************************************** */
/*  zft — libft tester (C rewrite, inspired by github.com/Caesarovich/zft)    */
/*  Framework header: test registration, assertions, helpers.                 */
/* ************************************************************************** */
#ifndef ZFT_H
# define ZFT_H

# ifndef _GNU_SOURCE
#  define _GNU_SOURCE
# endif
# include <stddef.h>
# include <stdint.h>
# include <stdio.h>
# include <stdlib.h>
# include <string.h>
# include <strings.h>
# include <limits.h>
# include <unistd.h>
# include <ctype.h>



/* ---------------------------------------------------------------- kinds -- */
typedef enum e_kind
{
	K_NORMAL,	/* assertions only; a crash is an error                      */
	K_VSREF,	/* run ft and the reference (real libc) in two processes and  */
				/* compare crash behaviour + output                           */
	K_MALLOC	/* run again with each malloc failing in turn                 */
}	t_kind;

typedef struct s_test
{
	const char	*func;
	const char	*name;
	t_kind		kind;
	int			spec;	/* NORMAL: whole test speculative.
						   VSREF : an output mismatch is only speculative     */
	void		(*fn)(void);
	const char	*file;
	int			line;
	int			seq;
	int			idx;	/* __COUNTER__ of the TEST in its file: lets
						   `torture ... --repro file#idx` rebuild it alone.
						   -1 for tests registered at run time.          */
	int			pos;	/* position in its suite, among the selected tests
						   (the "index" of its test event)                  */
	int			fuzz;	/* FUZZ_TEST: its FUZZ_LOOP may be cut in slices     */
	int			slice;	/* this copy runs slice `slice` of `slices` (--split) */
	int			slices;
}	t_test;

void	zft_register(const char *func, const char *name, t_kind kind, int spec,
			void (*fn)(void), const char *file, int line, int idx);

# define ZFT_CAT2(a, b) a##b
# define ZFT_CAT(a, b) ZFT_CAT2(a, b)

# define TEST_EX(F, NAME, KIND, SPEC) TEST_EX2(F, NAME, KIND, SPEC, __COUNTER__)
# define TEST_EX2(F, NAME, KIND, SPEC, N) \
	static void ZFT_CAT(zt_fn_, N)(void); \
	__attribute__((constructor)) static void ZFT_CAT(zt_reg_, N)(void) \
	{ zft_register(#F, NAME, KIND, SPEC, ZFT_CAT(zt_fn_, N), \
		__FILE__, __LINE__, N); } \
	static void ZFT_CAT(zt_fn_, N)(void)

/* Plain test with assertions.                                              */
# define TEST(F, NAME)      TEST_EX(F, NAME, K_NORMAL, 0)
/* A fuzzing test: its cases come from FUZZ_LOOP(k, N), each seeded by its
   number k. The normal pass runs it whole; the valgrind and sanitizer passes
   (engine --split N) run it in N slices at once, on exactly the same cases. */
# define FUZZ_TEST(F, NAME) TEST_EX(F, NAME, K_NORMAL, 2)
extern int	g_slice;
extern int	g_slices;
void		zft_fuzz(int k);
# define FUZZ_LOOP(k, n) for (int k = (int)((long)(n) * g_slice / g_slices); \
	k < (int)((long)(n) * (g_slice + 1) / g_slices) && (zft_fuzz(k), 1); k++)
/* Plain test whose expectation is not required by the subject.             */
# define SPEC_TEST(F, NAME) TEST_EX(F, NAME, K_NORMAL, 1)
/* ft vs real function. Crash rules:
     ft crash  + real crash  -> OK (same behaviour as the original)
     ft crash  + real ok     -> ERROR (even without --speculative)
     ft ok     + real crash  -> SPECULATIVE error (you protect, the libc does not)
     ft ok     + real ok     -> outputs (OUT) must match                       */
# define VS(F, NAME)        TEST_EX(F, NAME, K_VSREF, 0)
/* Same, but a mismatch of the outputs is only speculative (UB territory).  */
# define VS_SPEC(F, NAME)   TEST_EX(F, NAME, K_VSREF, 1)
/* Runs once to count mallocs done between ARM()/DISARM(), then once per
   malloc with that malloc returning NULL. Crash or leak = error.            */
# define MTEST(F, NAME)     TEST_EX(F, NAME, K_MALLOC, 0)

/* -------------------------------------------------------- runtime state -- */
extern int	g_ref;			/* 1 while running the reference implementation */
extern int	g_fail_at;		/* index of the malloc that must fail (0 = none) */
extern int	g_armed;		/* count mallocs only between ARM/DISARM         */

# define REF (g_ref)
# define FAILING (g_fail_at > 0)
/* Pick the function to call: PICK(ft_strlen, r_strlen)(s)                   */
# define PICK(ft, ref) (g_ref ? (ref) : (ft))
# define ARM() (g_armed = 1)
# define DISARM() (g_armed = 0)

/* ----------------------------------------------------------- benchmarks -- */
/* BENCH(F) { COST(...); BENCH_LOOP { ... } } : one workload of function F,
   run zb_n times, timed with --efficiency. COST() declares the MINIMAL work
   one repetition needs (what a perfect implementation cannot avoid); the
   engine turns it into a "perfect" time with costs measured on this
   machine, and compares it with your real time. Count the harness work
   inside the loop too (the mallocs it frees, the callbacks it passes).
   malloc is not instrumented during a benchmark.                           */
typedef struct s_cost
{
	double	iters;		/* turns of a loop that does nothing else listed    */
	double	calls;		/* function calls (yours, or a callback), on top   */
	double	ops;		/* comparisons / tiny arithmetic steps, on top     */
	double	scan;		/* bytes read and tested one by one                 */
	double	copy;		/* bytes copied one by one                          */
	double	store;		/* bytes written one by one                         */
	double	cmp;		/* bytes compared between two buffers               */
	double	digits;		/* decimal digits produced (one / and one % each)  */
	double	nodes;		/* list nodes walked                                */
	double	allocs;		/* malloc + free of a small block                   */
	double	big_allocs;	/* malloc + free of a block of several MiB (mmap)  */
	double	sys;		/* system calls (write, read)                       */
	double	rbytes;		/* bytes brought by read() from a file              */
}	t_cost;

void	zft_bench_register(const char *func, void (*fn)(long),
			const char *file, int line);
extern volatile long	g_bench_sink;	/* keeps results alive               */
extern t_cost			g_bench_cost;	/* set by COST() in the workload     */

# define BENCH(F) BENCH2(F, __COUNTER__)
# define BENCH2(F, N) \
	static void ZFT_CAT(zb_fn_, N)(long zb_n); \
	__attribute__((constructor)) static void ZFT_CAT(zb_reg_, N)(void) \
	{ zft_bench_register(#F, ZFT_CAT(zb_fn_, N), __FILE__, __LINE__); } \
	static void ZFT_CAT(zb_fn_, N)(long zb_n)
# define BENCH_LOOP for (long zb_i = 0; zb_i < zb_n; zb_i++)
# define SINK(x) (g_bench_sink += (long)(x))
# define COST(...) (g_bench_cost = (t_cost){__VA_ARGS__})

/* SCORE(F) { ... SCORE_SET(ideal, real); } : an efficiency that is not a
   time (push_swap: operations printed). Runs once, in a child; the result
   is ideal / real, shown like a benchmark with --efficiency.               */
void	zft_score_register(const char *func, void (*fn)(void),
			const char *file, int line);
extern double	g_score_ideal;
extern double	g_score_real;
# define SCORE(F) SCORE2(F, __COUNTER__)
# define SCORE2(F, N) \
	static void ZFT_CAT(zs_fn_, N)(void); \
	__attribute__((constructor)) static void ZFT_CAT(zs_reg_, N)(void) \
	{ zft_score_register(#F, ZFT_CAT(zs_fn_, N), __FILE__, __LINE__); } \
	static void ZFT_CAT(zs_fn_, N)(void)
# define SCORE_SET(ideal, real) (g_score_ideal = (ideal), g_score_real = (real))

/* Directory of the project under test (--path).                           */
const char	*zft_path(void);
/* 1 when the report is in English (messages written by a suite).          */
int			zft_en(void);
/* Call before a CHECK that fails: the failure counts as ▲ (speculative),
   decided at run time (push_swap: a 500 list in the medium regime).       */
void		zft_soft(void);

/* ----------------------------------------------------------- assertions -- */
__attribute__((noreturn)) void	zft_fail(const char *file, int line,
			const char *expr, const char *expected, const char *got);
__attribute__((noreturn, format(printf, 3, 4))) void	zft_failf(
			const char *file, int line, const char *fmt, ...);
__attribute__((format(printf, 1, 2))) void	zft_out(const char *fmt, ...);
__attribute__((format(printf, 1, 2))) void	zft_input(const char *fmt, ...);
void	zft_esc(char *dst, size_t dsz, const char *s, size_t n);
const char	*zft_str(const char *s);	/* escaped "..." or NULL (ring buffer) */
const char	*zft_mem(const void *p, size_t n);	/* hex dump (ring buffer)  */

/* Record a value for comparison with the reference (VS tests).             */
# define OUT(...) zft_out(__VA_ARGS__)
/* Describe the current input (shown when the test fails or crashes).       */
# define INPUT(...) zft_input(__VA_ARGS__)

# define CHECK(cond, ...) do { if (!(cond)) \
	zft_failf(__FILE__, __LINE__, __VA_ARGS__); } while (0)

# define EQ_INT(got, exp) do { long long zq_g = (long long)(got); \
	long long zq_e = (long long)(exp); if (zq_g != zq_e) { char zq_a[64], zq_b[64]; \
	snprintf(zq_a, 64, "%lld", zq_e); snprintf(zq_b, 64, "%lld", zq_g); \
	zft_fail(__FILE__, __LINE__, #got, zq_a, zq_b); } } while (0)

# define EQ_SZ(got, exp) do { size_t zq_g = (size_t)(got); \
	size_t zq_e = (size_t)(exp); if (zq_g != zq_e) { char zq_a[64], zq_b[64]; \
	snprintf(zq_a, 64, "%zu", zq_e); snprintf(zq_b, 64, "%zu", zq_g); \
	zft_fail(__FILE__, __LINE__, #got, zq_a, zq_b); } } while (0)

# define EQ_PTR(got, exp) do { const void *zq_g = (const void *)(got); \
	const void *zq_e = (const void *)(exp); if (zq_g != zq_e) { char zq_a[64], zq_b[64]; \
	snprintf(zq_a, 64, "%p", zq_e); snprintf(zq_b, 64, "%p", zq_g); \
	zft_fail(__FILE__, __LINE__, #got, zq_a, zq_b); } } while (0)

# define EQ_STR(got, exp) do { const char *zq_g = (got); const char *zq_e = (exp); \
	if ((zq_g == NULL) != (zq_e == NULL) || (zq_g && strcmp(zq_g, zq_e) != 0)) \
	zft_fail(__FILE__, __LINE__, #got, zft_str(zq_e), zft_str(zq_g)); } while (0)

# define EQ_MEM(got, exp, n) do { const void *zq_g = (got); const void *zq_e = (exp);\
	size_t zq_n = (n); if (memcmp(zq_g, zq_e, zq_n) != 0) \
	zft_fail(__FILE__, __LINE__, #got, zft_mem(zq_e, zq_n), zft_mem(zq_g, zq_n)); \
	} while (0)

# define SIGN(x) ((x) > 0 ? 1 : ((x) < 0 ? -1 : 0))

/* -------------------------------------------------------- memory helpers -- */
/* Guarded copies: the byte right after the data is an unmapped page, so any
   read past the end segfaults.                                             */
char	*gstr(const char *s);			/* "abc\0" + guard                  */
void	*gmem(const void *src, size_t n);	/* n bytes + guard (no '\0' added)  */
void	*gbuf(size_t n, int fill);			/* n bytes filled with fill + guard */
/* Size of the malloc block starting exactly at p, or (size_t)-1 if p is not
   the start of a live block allocated through malloc().                    */
size_t	alloc_size(const void *p);
int		zm_live_blocks(void);
void	real_free(void *p);				/* free memory allocated by the libc */
/* free() something returned by either ft_ (tracked) or the real libc       */
# define XFREE(p) (g_ref ? real_free(p) : free(p))

/* fd capture: returns a fd writing into a temp file; read it back with
   cap_read (returns a static, NUL-terminated buffer and its length).        */
int			cap_open(void);
const char	*cap_read(int fd, size_t *len);

/* deterministic PRNG */
uint32_t	zrand(void);
void		zsrand(uint32_t seed);

#endif
