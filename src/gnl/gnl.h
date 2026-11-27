/* ************************************************************************** */
/*  get_next_line tester helpers.                                             */
/*  The tester is rebuilt once per BUFFER_SIZE with:                          */
/*    -D BUFFER_SIZE=n -D Z_BS=n -D GNL_SUITE=bsN   (Z_BS=-1: default value)  */
/*  read() is wrapped (-Wl,--wrap=read): bytes are counted and one call can   */
/*  be forced to fail.                                                        */
/* ************************************************************************** */
#ifndef GNL_H
# define GNL_H

# include <sys/types.h>
# include "zft.h"

# ifndef Z_BS
#  define Z_BS 42
# endif
# ifndef GNL_SUITE
#  define GNL_SUITE bs42
# endif

char	*get_next_line(int fd) __attribute__((weak));

extern size_t	g_rd_bytes;		/* bytes returned by read() so far          */
extern int		g_rd_calls;		/* read() calls so far                      */
extern int		g_rd_fail_at;	/* this read() call returns -1 (0 = never)  */
extern int		g_rd_short;		/* 1: read() returns 1 to n bytes at random */

/* temp file containing data (already unlinked), opened O_RDONLY */
int		gnl_file(const char *data, size_t len);

/* one fd being read, with the content it is expected to return */
typedef struct s_gnl
{
	int			fd;
	const char	*data;
	size_t		len;
	size_t		pos;
	int			line;
	int			done;
	const char	*what;
}	t_gnl;

void	gnl_init(t_gnl *g, int fd, const char *data, size_t len,
			const char *what);
/* one get_next_line() call checked against the next expected line; at the
   end, checks NULL twice. Returns 0 once the fd is finished.              */
int		gnl_step(const char *file, int line, t_gnl *g);
/* read the whole fd */
void	gnl_expect(const char *file, int line, int fd, const char *data,
			size_t len, const char *what);

# define EXPECT_FD(fd, d, n, what) gnl_expect(__FILE__, __LINE__, fd, d, n, what)
# define STEP(g) gnl_step(__FILE__, __LINE__, g)

#endif
