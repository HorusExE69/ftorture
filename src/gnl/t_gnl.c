/* ************************************************************************** */
/*  get_next_line — MANDATORY PART (subject v14.3)                            */
/*  Built once per BUFFER_SIZE; every test lands in the suite GNL_SUITE      */
/*  (one report line per BUFFER_SIZE). Each line returned is compared with   */
/*  the expected one, must be a malloc block, and is freed; after the last   */
/*  line get_next_line must return NULL (twice). Leaks are checked.           */
/* ************************************************************************** */
#include <fcntl.h>
#include <sys/wait.h>
#include <signal.h>
#include "gnl.h"

/* BUFFER_SIZE used to build lines around the buffer size */
#define T_(fr, en) (zft_en() ? (en) : (fr))
#define BS (Z_BS > 0 ? Z_BS : 42)
/* sizes that stay reasonable even with BUFFER_SIZE=10000000 */
#define SMALL_BS (Z_BS > 0 && Z_BS <= 100000)
/* Very long lines are cut to 4096 read() calls: with BUFFER_SIZE=1, a stash
   rebuilt by a strjoin after every read() is quadratic (100 000 characters
   take minutes). 4096 reads still check the accumulation; the "too slow"
   test below and -e report the cost instead of a timeout.               */
#define READS_MAX 4096
#define LONG(n) ((size_t)(n) < (size_t)BS * READS_MAX ? (size_t)(n) \
	: (size_t)BS * READS_MAX)

#define FILE_TEST(NAME, DATA) \
TEST(GNL_SUITE, NAME) \
{ \
	static const char	d[] = DATA; \
	int					fd = gnl_file(d, sizeof(d) - 1); \
	EXPECT_FD(fd, d, sizeof(d) - 1, NAME); \
	close(fd); \
}

#if Z_BS == 0

/* BUFFER_SIZE=0 makes no sense: only "no crash, no leak" is checked (▲) */
TEST(GNL_SUITE, "BUFFER_SIZE=0 : NULL, sans crash ni fuite")
{
	int		fd = gnl_file("abc\ndef\n", 8);
	char	*r = get_next_line(fd);

	INPUT("get_next_line(fd) compilé avec -D BUFFER_SIZE=0");
	CHECK(r == NULL, "avec BUFFER_SIZE=0, get_next_line devrait renvoyer NULL");
	free(r);
	close(fd);
}

#else

/* ---------------------------------------------------------- contents -- */
FILE_TEST("fichier vide", "")
FILE_TEST("une ligne avec \\n", "hello\n")
FILE_TEST("une ligne sans \\n", "hello")
FILE_TEST("un seul \\n", "\n")
FILE_TEST("que des \\n", "\n\n\n\n\n")
FILE_TEST("un seul caractère", "x")
FILE_TEST("plusieurs lignes", "ligne 1\nligne 2\n\nligne 4\n")
FILE_TEST("dernière ligne sans \\n", "a\nb\nc")
FILE_TEST("lignes vides au milieu et à la fin", "a\n\n\nb\n\n")
FILE_TEST("caractères spéciaux et non-ASCII", "\t tab\r\n\x7f\x01\n\xe9t\xe9 \xff\n")
FILE_TEST("texte réaliste", "Lorem ipsum dolor sit amet,\nconsectetur adipiscing "
	"elit.\n\nSed do eiusmod tempor incididunt\nut labore et dolore magna "
	"aliqua.\nUt enim ad minim veniam")

/* lines of length n (+ '\n' or not) */
static void	run_len(const char *file, int line, size_t n, int nl, int count)
{
	size_t	tot = (n + (size_t)nl) * (size_t)count;
	char	*d = gbuf(tot ? tot : 1, 0);
	size_t	k = 0;
	int		fd;
	char	what[96];

	for (int c = 0; c < count; c++)
	{
		for (size_t i = 0; i < n; i++)
			d[k++] = (char)('a' + (i + (size_t)c) % 26);
		if (nl)
			d[k++] = '\n';
	}
	snprintf(what, sizeof(what), "%d ligne(s) de %zu car.%s", count, n,
		nl ? " + \\n" : " sans \\n");
	fd = gnl_file(d, tot);
	gnl_expect(file, line, fd, d, tot, what);
	close(fd);
}
#define LEN(n, nl, count) run_len(__FILE__, __LINE__, n, nl, count)

TEST(GNL_SUITE, "lignes de BUFFER_SIZE - 1, BUFFER_SIZE, BUFFER_SIZE + 1")
{
	if (!SMALL_BS)
	{
		LEN(100, 1, 3);
		return ;
	}
	if (BS > 1)
		LEN(BS - 1, 1, 3);
	LEN(BS, 1, 3);
	LEN(BS + 1, 1, 3);
}
TEST(GNL_SUITE, "pareil, sans \\n final")
{
	if (!SMALL_BS)
	{
		LEN(100, 0, 1);
		return ;
	}
	if (BS > 1)
		LEN(BS - 1, 0, 1);
	LEN(BS, 0, 1);
	LEN(BS + 1, 0, 1);
}
TEST(GNL_SUITE, "lignes de 2 x BUFFER_SIZE et plus")
{
	if (!SMALL_BS || BS > 20000)
	{
		LEN(5000, 1, 2);
		return ;
	}
	LEN(2 * BS, 1, 2);
	LEN(3 * BS + 7, 1, 2);
}
TEST(GNL_SUITE, "ligne longue (10 000 caractères)")   { LEN(10000, 1, 2); LEN(10000, 0, 1); }
TEST(GNL_SUITE, "ligne très longue (jusqu'à 100 000)") { LEN(LONG(100000), 1, 1); }

/* the real 100 000 characters, stopped after 3 s instead of a timeout     */
static void	too_slow(int sig)
{
	(void)sig;
	zft_failf(__FILE__, __LINE__, "%s", zft_en()
		? "not done after 3 s: a 100 000 character line costs too much (a "
		"stash rebuilt by a strjoin after every read() is quadratic; the "
		"same line shorter passed above, see the efficiency with -e)"
		: "pas fini en 3 s : une ligne de 100 000 caractères coûte trop cher "
		"(une stash refaite par un strjoin après chaque read() est "
		"quadratique ; la même ligne plus courte est passée au-dessus, "
		"regarde l'efficacité avec -e)");
}

SPEC_TEST(GNL_SUITE, "ligne de 100 000 en moins de 3 s")
{
	signal(SIGALRM, too_slow);
	alarm(3);
	LEN(100000, 1, 1);
	alarm(0);
}
TEST(GNL_SUITE, "5 000 lignes d'un caractère")        { LEN(1, 1, 5000); }
TEST(GNL_SUITE, "gros fichier (~80 Ko, longueurs variées)")
{
	size_t	cap = 90000;
	char	*d = gbuf(cap, 0);
	size_t	k = 0;
	int		fd;

	while (k < 80000)
	{
		size_t	l = zrand() % 160;

		for (size_t i = 0; i < l; i++)
			d[k++] = (char)(' ' + zrand() % 95);
		d[k++] = '\n';
	}
	fd = gnl_file(d, k);
	EXPECT_FD(fd, d, k, "gros fichier");
	close(fd);
}

/* The King James Bible (4.3 MB, 99 594 lines, built by the runner from
   data/bible-kjv.txt.gz): a real big text file, with a buffer that makes
   sense for it. 32 to 10 000 (and the default): the whole book. Below 32:
   its first BUFFER_SIZE x 50 000 bytes, so 1 byte per read() stays quick.
   Above 10 000: its first 100 KB, since a buffer that big keeps up to a
   buffer of text in the stash, and a stash moved after every line copies
   it 99 594 times (100K: 5 GB). Each cut is at a line end.             */
#ifdef Z_BIBLE
# if Z_BS < 0 || (Z_BS >= 32 && Z_BS <= 10000)
#  define BIBLE_NAME "la Bible entière (King James, 4,3 Mo)"
#  define BIBLE_KEEP ((size_t)-1)
# elif Z_BS < 32
#  define BIBLE_NAME "la Bible, début (BUFFER_SIZE × 50 000 octets)"
#  define BIBLE_KEEP ((size_t)Z_BS * 50000)
# else
#  define BIBLE_NAME "la Bible, début (100 Ko : buffer > 10 000)"
#  define BIBLE_KEEP ((size_t)100000)
# endif

TEST(GNL_SUITE, BIBLE_NAME)
{
	int			in = open(Z_BIBLE, O_RDONLY);
	off_t		size = in >= 0 ? lseek(in, 0, SEEK_END) : -1;
	char		*d;
	size_t		n = 0;
	size_t		keep;
	int			fd;

	CHECK(size > 0, "%s : %s", Z_BIBLE, T_("introuvable (tester)", "missing (tester)"));
	lseek(in, 0, SEEK_SET);
	d = malloc((size_t)size);
	while (d && n < (size_t)size)
	{
		ssize_t	r = read(in, d + n, (size_t)size - n);

		if (r <= 0)
			break ;
		n += (size_t)r;
	}
	close(in);
	keep = n;
	if (BIBLE_KEEP < n)
	{
		keep = BIBLE_KEEP;
		while (keep < n && d[keep - 1] != '\n')
			keep++;
	}
	fd = gnl_file(d, keep);
	EXPECT_FD(fd, d, keep, keep == n ? "la Bible (King James)"
		: "le début de la Bible (King James)");
	close(fd);
	free(d);
}
#endif

/* ------------------------------------------------------- other fds ---- */
TEST(GNL_SUITE, "entrée standard (fd 0)")
{
	static const char	d[] = "lu depuis stdin\nligne 2\nfin sans newline";
	int					fd = gnl_file(d, sizeof(d) - 1);

	dup2(fd, 0);
	close(fd);
	EXPECT_FD(0, d, sizeof(d) - 1, "stdin");
}
TEST(GNL_SUITE, "pipe alimenté par petits morceaux")
{
	static char	d[6000];
	size_t		len = 0;
	int			p[2];
	pid_t		pid;

	while (len < 5500)
	{
		size_t	l = zrand() % 80;

		for (size_t i = 0; i < l; i++)
			d[len++] = (char)('a' + zrand() % 26);
		d[len++] = '\n';
	}
	d[len++] = 'z';
	if (pipe(p) < 0)
		zft_failf(__FILE__, __LINE__, "pipe a échoué (tester)");
	pid = fork();
	if (pid == 0)
	{
		size_t	o = 0;

		close(p[0]);
		while (o < len)
		{
			size_t	k = 1 + zrand() % 37;

			if (k > len - o)
				k = len - o;
			if (write(p[1], d + o, k) <= 0)
				_exit(1);
			o += k;
			if (zrand() % 8 == 0)
				usleep(200);
		}
		_exit(0);
	}
	close(p[1]);
	EXPECT_FD(p[0], d, len, "pipe (écritures de 1 à 37 octets)");
	close(p[0]);
	waitpid(pid, NULL, 0);
}
TEST(GNL_SUITE, "fd invalides : -1, non ouvert, fermé")
{
	int		fd = gnl_file("abc\n", 4);
	char	*r;

	close(fd);
	INPUT("get_next_line(-1)");
	r = get_next_line(-1);
	CHECK(r == NULL, "get_next_line(-1) doit renvoyer NULL");
	INPUT("get_next_line(4242) (fd jamais ouvert)");
	r = get_next_line(4242);
	CHECK(r == NULL, "get_next_line(4242) doit renvoyer NULL");
	INPUT("get_next_line(fd fermé)");
	r = get_next_line(fd);
	CHECK(r == NULL, "get_next_line sur un fd fermé doit renvoyer NULL");
}
TEST(GNL_SUITE, "fd très grands : 1024, 10 000, 65 535, INT_MAX")
{
	static const int	fds[] = {1024, 10000, 65535, INT_MAX, -42, INT_MIN};
	char				*r;

	/* a bonus array stash[fd] indexed without a bound check writes far
	   outside it: NULL is expected, without a crash                      */
	for (size_t k = 0; k < sizeof(fds) / sizeof(*fds); k++)
	{
		INPUT("get_next_line(%d)", fds[k]);
		r = get_next_line(fds[k]);
		CHECK(r == NULL, "fd %d jamais ouvert : NULL attendu, reçu %s", fds[k],
			zft_str(r));
	}
}
TEST(GNL_SUITE, "fd ouvert en écriture seule (read échoue)")
{
	char	path[] = "/tmp/ftorture_gnl_woXXXXXX";
	int		fd = mkstemp(path);
	char	*r;

	if (fd >= 0)
		write(fd, "abc\n", 4);
	close(fd);
	fd = open(path, O_WRONLY);
	unlink(path);
	INPUT("fd ouvert avec O_WRONLY sur \"abc\\n\"");
	r = get_next_line(fd);
	CHECK(r == NULL, "read() échoue (EBADF) : NULL attendu, reçu %s", zft_str(r));
	r = get_next_line(fd);
	CHECK(r == NULL, "rappel : NULL attendu, reçu %s", zft_str(r));
	close(fd);
}
TEST(GNL_SUITE, "/dev/null : NULL tout de suite")
{
	int		fd = open("/dev/null", O_RDONLY);
	char	*r;

	INPUT("get_next_line(open(\"/dev/null\"))");
	r = get_next_line(fd);
	CHECK(r == NULL, "fichier vide : NULL attendu, reçu %s", zft_str(r));
	close(fd);
}
FILE_TEST("fins de ligne \\r\\n", "ligne 1\r\nligne 2\r\n\r\nfin\r")
FILE_TEST("lignes vides au début", "\n\n\nabc\ndef")
TEST(GNL_SUITE, "tous les octets sauf \\0")
{
	char	d[600];
	size_t	k = 0;
	int		fd;

	for (int r = 0; r < 2; r++)
		for (int c = 1; c < 256; c++)
			d[k++] = (char)c;	/* '\n' (10) ends the lines on its own */
	fd = gnl_file(d, k);
	EXPECT_FD(fd, d, k, "octets 1 à 255, deux fois");
	close(fd);
}
TEST(GNL_SUITE, "même numéro de fd réutilisé après la fin")
{
	static const char	a[] = "premier\nfichier\n";
	static const char	b[] = "second\nfichier, autre contenu\n";
	int					fa = gnl_file(a, sizeof(a) - 1);
	int					fb;

	EXPECT_FD(fa, a, sizeof(a) - 1, "fichier A lu jusqu'au bout");
	/* the next file gets the same number: nothing of A may come back */
	fb = gnl_file(b, sizeof(b) - 1);
	if (fb != fa)
	{
		dup2(fb, fa);
		close(fb);
	}
	EXPECT_FD(fa, b, sizeof(b) - 1, "fichier B sur le même fd que A");
	close(fa);
}
TEST(GNL_SUITE, "read() renvoie moins que demandé (lectures partielles)")
{
	size_t	cap = 30000;
	char	*d = gbuf(cap, 0);
	size_t	k = 0;
	int		fd;

	while (k < cap - 300)
	{
		size_t	l = zrand() % (BS < 200 ? (size_t)BS * 3 + 2 : 300);

		for (size_t i = 0; i < l; i++)
			d[k++] = (char)('a' + zrand() % 26);
		d[k++] = '\n';
	}
	fd = gnl_file(d, k);
	g_rd_short = 1;
	EXPECT_FD(fd, d, k, "read() de 1 à BUFFER_SIZE octets au hasard");
	g_rd_short = 0;
	close(fd);
}
TEST(GNL_SUITE, "un dossier (read échoue avec EISDIR)")
{
	int		fd = open("/tmp", O_RDONLY);
	char	*r;

	INPUT("get_next_line(open(\"/tmp\"))");
	r = get_next_line(fd);
	CHECK(r == NULL, "lire un dossier doit renvoyer NULL");
	close(fd);
}
TEST(GNL_SUITE, "un fd invalide puis un fichier normal")
{
	static const char	d[] = "premier\nsecond\n";
	int					fd;

	free(get_next_line(-1));
	fd = gnl_file(d, sizeof(d) - 1);
	EXPECT_FD(fd, d, sizeof(d) - 1, "après get_next_line(-1)");
	close(fd);
}

/* --------------------------------------------------------- errors ----- */
#if SMALL_BS
TEST(GNL_SUITE, "read() échoue au milieu : NULL, puis repart de zéro")
{
	/* line 2 is longer than 2 x BUFFER_SIZE, so it needs more read() calls */
	size_t	l2 = (size_t)BS * 2 + 10;
	size_t	tot = 2 + l2 + 1;
	char	*d = gbuf(tot, 'x');
	int		fd;
	char	*r;
	t_gnl	g;
	static const char	d2[] = "nouveau\nfichier\n";

	d[0] = 'a';
	d[1] = '\n';
	d[tot - 1] = '\n';
	fd = gnl_file(d, tot);
	gnl_init(&g, fd, d, tot, "read() renverra -1 après la 1re ligne");
	STEP(&g);
	g_rd_fail_at = g_rd_calls + 1;
	INPUT("2e appel : le prochain read() renvoie -1");
	r = get_next_line(fd);
	g_rd_fail_at = 0;
	if (r && strlen(r) == l2 + 1)
	{
		free(r);	/* the line was already in the stash: no read needed */
		close(fd);
		return ;
	}
	CHECK(r == NULL, "quand read() renvoie -1, get_next_line doit renvoyer "
		"NULL (reçu %s)", zft_str(r));
	close(fd);
	fd = gnl_file(d2, sizeof(d2) - 1);
	EXPECT_FD(fd, d2, sizeof(d2) - 1,
		"nouveau fichier après l'erreur (le reste doit avoir été libéré)");
	close(fd);
}
TEST(GNL_SUITE, "lit le minimum (pas tout le fichier d'un coup)")
{
	size_t	tot = 6 + LONG(300000) + 1;
	char	*d = gbuf(tot, 'x');
	int		fd;
	char	*r;
	size_t	bound = ((6 + (size_t)BS - 1) / (size_t)BS) * (size_t)BS;

	memcpy(d, "short\n", 6);
	d[tot - 1] = '\n';
	fd = gnl_file(d, tot);
	g_rd_bytes = 0;
	INPUT("1er appel sur \"short\\n\" + %zu caractères", tot - 7);
	r = get_next_line(fd);
	CHECK(r && !strcmp(r, "short\n"), "1re ligne attendue \"short\\n\", reçu %s",
		zft_str(r));
	CHECK(g_rd_bytes <= bound, "%zu octets lus pour renvoyer une ligne de 6 "
		"octets (max attendu : %zu, soit des read() de BUFFER_SIZE jusqu'au "
		"premier \\n)", g_rd_bytes, bound);
	free(r);
	while ((r = get_next_line(fd)))
		free(r);
	close(fd);
}
#endif

MTEST(GNL_SUITE, "malloc échoue : pas de crash ni de fuite")
{
	static const char	d[] = "abc\ndefgh\nij";
	int					fd = gnl_file(d, sizeof(d) - 1);
	char				*l;

	ARM();
	while ((l = get_next_line(fd)))
		free(l);
	DISARM();
	close(fd);
}

#endif
