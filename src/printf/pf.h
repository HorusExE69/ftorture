/* ************************************************************************** */
/*  ft_printf tester helpers.                                                 */
/*  PF(fmt, args...) runs ft_printf then the real printf with the SAME        */
/*  arguments, each with fd 1 redirected to a temp file, and compares the     */
/*  bytes written AND the return value.                                       */
/* ************************************************************************** */
#ifndef PF_H
# define PF_H

# include "zft.h"

int		ft_printf(const char *fmt, ...) __attribute__((weak));
/* the real printf, through a volatile pointer: no format checking, no
   compile-time folding, so undefined cases really reach the libc         */
extern int	(*volatile r_printf)(const char *fmt, ...);

typedef struct s_cap
{
	char	buf[65536];
	size_t	len;
	int		ret;
}	t_cap;

extern t_cap	g_pf_ft;
extern t_cap	g_pf_rl;

int		pf_begin(int *saved);
void	pf_end(int fd, int saved, t_cap *c);
void	pf_compare(const char *file, int line, const t_cap *ft,
			const t_cap *rl);

# define PF_RUN(dst, call) do { int zq_sv; int zq_fd = pf_begin(&zq_sv); \
	(dst).ret = (call); pf_end(zq_fd, zq_sv, &(dst)); } while (0)

/* PF("%d|%s", 42, "abc") : same output and same return value as printf */
# define PF(...) do { INPUT("ft_printf(%s)", #__VA_ARGS__); \
	PF_RUN(g_pf_ft, ft_printf(__VA_ARGS__)); \
	PF_RUN(g_pf_rl, r_printf(__VA_ARGS__)); \
	pf_compare(__FILE__, __LINE__, &g_pf_ft, &g_pf_rl); } while (0)

/* runtime formats (fuzzing): one typed argument */
void	pf_one_i(const char *file, int line, const char *fmt, int v);
void	pf_one_u(const char *file, int line, const char *fmt, unsigned v);
void	pf_one_s(const char *file, int line, const char *fmt, const char *v);
void	pf_one_p(const char *file, int line, const char *fmt, void *v);
void	pf_one_c(const char *file, int line, const char *fmt, int v);

/* An int argument whose 64-bit slot has garbage in its upper half: on x86-64
   an int is passed in a 64-bit register or stack slot and only its low 32
   bits are defined. va_arg(ap, int) / (unsigned int) reads exactly those;
   va_arg(ap, long) / (unsigned long) reads the garbage too. The moulinette's
   calls often leave such garbage, the tester's own calls usually do not.   */
# define DIRTY(v) ((long)(0x5a5a5a5a00000000UL | (unsigned int)(v)))
/* ft_printf(fmt, DIRTY(v)) must print what printf(fmt, v) prints          */
void	pf_dirty(const char *file, int line, const char *fmt, int v);
/* 8 arguments: the last ones go on the stack (4 bytes written, 8 read)     */
void	pf_dirty8(const char *file, int line, const char *fmt, const int *v);
/* fmt with up to 8 conversions of cspdiuxX%, one 64-bit slot per argument  */
void	pf_multi(const char *file, int line, const char *fmt, const long *a);

/* random building blocks */
int			pf_rand_int(void);
unsigned	pf_rand_uint(void);
void		*pf_rand_ptr(void);
const char	*pf_rand_str(void);

#endif
