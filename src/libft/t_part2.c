/* ************************************************************************** */
/*  PART 2 — additional functions.                                            */
/*  No libc original exists: the "real" function is an unprotected reference */
/*  implementation (refs.c). NULL arguments: if the reference crashes and     */
/*  yours does not, it is only a speculative remark.                          */
/* ************************************************************************** */
#include "zft.h"
#include "libft_decl.h"
#include "refs.h"

static void	free_split(char **r)
{
	if (!r)
		return ;
	for (size_t i = 0; r[i]; i++)
		free(r[i]);
	free(r);
}

static void	out_split(char **r)
{
	if (!r)
	{
		OUT("NULL");
		return ;
	}
	for (size_t i = 0; r[i]; i++)
		OUT("%s", zft_str(r[i]));
	OUT("NULL");
}

static void	check_str_alloc(const char *file, int line, const char *r)
{
	size_t	sz = alloc_size(r);

	if (sz == (size_t)-1)
		zft_failf(file, line, "le résultat n'est pas un bloc alloué par malloc");
	if (sz < strlen(r) + 1)
		zft_failf(file, line, "bloc trop petit : %zu octet(s) alloué(s) pour "
			"une chaîne de %zu caractère(s) (+1 pour le '\\0')", sz, strlen(r));
}
#define STR_ALLOC(r) check_str_alloc(__FILE__, __LINE__, (r))

static void	check_exact(const char *file, int line, const char *r)
{
	size_t	sz = alloc_size(r);

	if (sz != strlen(r) + 1)
		zft_failf(file, line, "alloue %zu octet(s) au lieu de %zu "
			"(gaspillage, pas une erreur)", sz, strlen(r) + 1);
}
#define EXACT_ALLOC(r) check_exact(__FILE__, __LINE__, (r))

static void	rand_str(char *b, size_t max, const char *alpha)
{
	size_t	l = zrand() % max;
	size_t	na = strlen(alpha);

	for (size_t i = 0; i < l; i++)
		b[i] = alpha[zrand() % na];
	b[l] = 0;
}

/* ========================================================== substr ===== */
#define SUB(s, st, ln, exp) do { \
	INPUT("ft_substr(%s, %u, %zu)", zft_str(s), (unsigned)(st), (size_t)(ln)); \
	char *_r = ft_substr(gstr(s), st, ln); \
	CHECK(_r != NULL, "a renvoyé NULL"); \
	EQ_STR(_r, exp); STR_ALLOC(_r); free(_r); } while (0)

TEST(ft_substr, "milieu")                    { SUB("Hello World", 6, 5, "World"); SUB("Hello World", 2, 3, "llo"); }
TEST(ft_substr, "chaîne entière")            { SUB("42", 0, 2, "42"); }
TEST(ft_substr, "len dépasse la fin")        { SUB("hola", 2, 100, "la"); SUB("hola", 0, SIZE_MAX, "hola"); }
TEST(ft_substr, "len = 0 -> \"\"")           { SUB("hola", 1, 0, ""); }
TEST(ft_substr, "start == strlen -> \"\"")   { SUB("hola", 4, 3, ""); }
TEST(ft_substr, "start > strlen -> \"\" sans lire hors de s") { SUB("hola", 10, 3, ""); SUB("", 1, 1, ""); SUB("abc", UINT_MAX, 5, ""); }
TEST(ft_substr, "s vide")                    { SUB("", 0, 5, ""); }
SPEC_TEST(ft_substr, "n'alloue que le nécessaire (len énorme)")
{
	char	*r = ft_substr("hola", 1, 1000);

	CHECK(r != NULL, "a renvoyé NULL");
	EXACT_ALLOC(r);
	free(r);
}
SPEC_TEST(ft_substr, "start > strlen : alloue 1 octet")
{
	char	*r = ft_substr("hola", 10, 1000);

	CHECK(r != NULL, "a renvoyé NULL");
	EXACT_ALLOC(r);
	free(r);
}
FUZZ_TEST(ft_substr, "aléatoire vs référence (2000 cas)")
{
	char	s[40];

	FUZZ_LOOP(k, 2000)
	{
		unsigned	st = zrand() % 45;
		size_t		ln = zrand() % 45;
		char		*a;
		char		*b;

		rand_str(s, 40, "abcdef");
		INPUT("ft_substr(%s, %u, %zu)", zft_str(s), st, ln);
		a = ft_substr(s, st, ln);
		b = r_substr(s, st, ln);
		EQ_STR(a, b);
		free(a);
		free(b);
	}
}
MTEST(ft_substr, "malloc échoue -> NULL")
{
	char	*r;

	ARM();
	r = ft_substr("Hello World", 3, 5);
	DISARM();
	if (FAILING)
		CHECK(r == NULL, "doit renvoyer NULL si malloc échoue");
	free(r);
}
VS(ft_substr, "s NULL")
{
	char	*r = PICK(ft_substr, r_substr)(NULL, 0, 5);

	OUT("%s", zft_str(r));
	free(r);
}

/* ========================================================= strjoin ===== */
#define JOIN(a, b, exp) do { \
	INPUT("ft_strjoin(%s, %s)", zft_str(a), zft_str(b)); \
	char *_r = ft_strjoin(gstr(a), gstr(b)); \
	CHECK(_r != NULL, "a renvoyé NULL"); \
	EQ_STR(_r, exp); STR_ALLOC(_r); free(_r); } while (0)

TEST(ft_strjoin, "concat simple")    { JOIN("Hello, ", "World", "Hello, World"); }
TEST(ft_strjoin, "s1 vide / s2 vide") { JOIN("", "abc", "abc"); JOIN("abc", "", "abc"); }
TEST(ft_strjoin, "les deux vides")   { JOIN("", "", ""); }
TEST(ft_strjoin, "non-ASCII")        { JOIN("\xe9t\xe9", "\xff\x80", "\xe9t\xe9\xff\x80"); }
TEST(ft_strjoin, "nouvelle zone, entrées intactes")
{
	char	*a = gstr("abc");
	char	*b = gstr("def");
	char	*r = ft_strjoin(a, b);

	CHECK(r != a && r != b, "doit renvoyer une nouvelle zone");
	EQ_STR(a, "abc");
	EQ_STR(b, "def");
	free(r);
}
SPEC_TEST(ft_strjoin, "taille exacte")
{
	char	*r = ft_strjoin("abc", "de");

	CHECK(r != NULL, "a renvoyé NULL");
	EXACT_ALLOC(r);
	free(r);
}
MTEST(ft_strjoin, "malloc échoue -> NULL")
{
	char	*r;

	ARM();
	r = ft_strjoin("Hello ", "World");
	DISARM();
	if (FAILING)
		CHECK(r == NULL, "doit renvoyer NULL si malloc échoue");
	free(r);
}
VS(ft_strjoin, "s1 NULL")
{
	char	*r = PICK(ft_strjoin, r_strjoin)(NULL, "abc");

	OUT("%s", zft_str(r));
	free(r);
}
VS(ft_strjoin, "s2 NULL")
{
	char	*r = PICK(ft_strjoin, r_strjoin)("abc", NULL);

	OUT("%s", zft_str(r));
	free(r);
}
VS(ft_strjoin, "s1 et s2 NULL")
{
	char	*r = PICK(ft_strjoin, r_strjoin)(NULL, NULL);

	OUT("%s", zft_str(r));
	free(r);
}

/* ========================================================= strtrim ===== */
#define TRIM(s, set, exp) do { \
	INPUT("ft_strtrim(%s, %s)", zft_str(s), zft_str(set)); \
	char *_r = ft_strtrim(gstr(s), gstr(set)); \
	CHECK(_r != NULL, "a renvoyé NULL"); \
	EQ_STR(_r, exp); STR_ALLOC(_r); free(_r); } while (0)

TEST(ft_strtrim, "début et fin")           { TRIM("  xxhelloxx  ", " x", "hello"); }
TEST(ft_strtrim, "garde le milieu")         { TRIM("--a-b--c--", "-", "a-b--c"); }
TEST(ft_strtrim, "tout est retiré -> \"\"") { TRIM("xxxx", "x", ""); TRIM("   ", " ", ""); }
TEST(ft_strtrim, "set vide -> copie")       { TRIM("  abc  ", "", "  abc  "); }
TEST(ft_strtrim, "s1 vide")                 { TRIM("", "abc", ""); TRIM("", "", ""); }
TEST(ft_strtrim, "rien à retirer")          { TRIM("hello", "xyz", "hello"); }
TEST(ft_strtrim, "un seul caractère")       { TRIM("a", "a", ""); TRIM("b", "a", "b"); }
TEST(ft_strtrim, "set multi-caractères")    { TRIM("\t\n hello world \n\t", " \t\n", "hello world"); }
SPEC_TEST(ft_strtrim, "taille exacte")
{
	char	*r = ft_strtrim("   abc   ", " ");

	CHECK(r != NULL, "a renvoyé NULL");
	EXACT_ALLOC(r);
	free(r);
}
FUZZ_TEST(ft_strtrim, "aléatoire vs référence (2000 cas)")
{
	char	s[30];
	char	set[5];

	FUZZ_LOOP(k, 2000)
	{
		char	*a;
		char	*b;

		rand_str(s, 30, "ab c");
		rand_str(set, 5, "a c");
		INPUT("ft_strtrim(%s, %s)", zft_str(s), zft_str(set));
		a = ft_strtrim(s, set);
		b = r_strtrim(s, set);
		EQ_STR(a, b);
		free(a);
		free(b);
	}
}
MTEST(ft_strtrim, "malloc échoue -> NULL")
{
	char	*r;

	ARM();
	r = ft_strtrim("  abc  ", " ");
	DISARM();
	if (FAILING)
		CHECK(r == NULL, "doit renvoyer NULL si malloc échoue");
	free(r);
}
VS(ft_strtrim, "s1 NULL")
{
	char	*r = PICK(ft_strtrim, r_strtrim)(NULL, " ");

	OUT("%s", zft_str(r));
	free(r);
}
VS(ft_strtrim, "set NULL")
{
	char	*r = PICK(ft_strtrim, r_strtrim)(" abc ", NULL);

	OUT("%s", zft_str(r));
	free(r);
}

/* =========================================================== split ===== */
static void	split_check(const char *file, int line, const char *s, char c,
				const char **exp)
{
	char	**r;
	size_t	n = 0;

	INPUT("ft_split(%s, '%s')", zft_str(s), c ? (char[2]){c, 0} : "\\0");
	r = ft_split(gstr(s), c);
	if (!r)
		zft_failf(file, line, "a renvoyé NULL");
	while (exp[n])
		n++;
	if (alloc_size(r) == (size_t)-1 || alloc_size(r) < (n + 1) * sizeof(char *))
		zft_failf(file, line, "le tableau doit être alloué avec malloc et "
			"contenir %zu pointeurs (NULL final compris)", n + 1);
	for (size_t i = 0; i <= n; i++)
	{
		if (!exp[i] && r[i])
			zft_fail(file, line, "r[i] (NULL final)", "NULL", zft_str(r[i]));
		if (exp[i] && !r[i])
			zft_fail(file, line, "r[i]", zft_str(exp[i]), "NULL (trop tôt)");
		if (exp[i] && strcmp(r[i], exp[i]))
			zft_fail(file, line, "r[i]", zft_str(exp[i]), zft_str(r[i]));
		if (exp[i])
			check_str_alloc(file, line, r[i]);
	}
	free_split(r);
}
#define SPLIT(s, c, ...) split_check(__FILE__, __LINE__, s, c, \
	(const char *[]){__VA_ARGS__})

TEST(ft_split, "simple")                    { SPLIT("Hello,World,Test", ',', "Hello", "World", "Test", NULL); }
TEST(ft_split, "délimiteurs consécutifs")  { SPLIT("a,,b,,,c", ',', "a", "b", "c", NULL); }
TEST(ft_split, "délimiteurs au début/fin") { SPLIT(",,,a,b,,,", ',', "a", "b", NULL); SPLIT("  lorem   ipsum  ", ' ', "lorem", "ipsum", NULL); }
TEST(ft_split, "que des délimiteurs -> {NULL}") { SPLIT(",,,,", ',', NULL); SPLIT(",", ',', NULL); }
TEST(ft_split, "chaîne vide -> {NULL}")    { SPLIT("", ',', NULL); SPLIT("", '\0', NULL); }
TEST(ft_split, "pas de délimiteur")        { SPLIT("hello", ' ', "hello", NULL); }
TEST(ft_split, "c = '\\0'")                { SPLIT("hello world", '\0', "hello world", NULL); }
TEST(ft_split, "mots d'une lettre")        { SPLIT("a b c d", ' ', "a", "b", "c", "d", NULL); }
TEST(ft_split, "délimiteur non-ASCII")     { SPLIT("ab\xff" "cd\xff\xff" "e", '\xff', "ab", "cd", "e", NULL); }
TEST(ft_split, "long (1000 mots)")
{
	char	*s = gbuf(2001, 'w');
	char	**r;
	size_t	n = 0;

	for (int i = 1; i < 2000; i += 2)
		s[i] = ' ';
	s[2000] = 0;
	r = ft_split(s, ' ');
	CHECK(r != NULL, "a renvoyé NULL");
	while (r[n])
	{
		EQ_STR(r[n], "w");
		n++;
	}
	EQ_SZ(n, 1000);
	free_split(r);
}
FUZZ_TEST(ft_split, "aléatoire vs référence (2000 cas)")
{
	char	s[40];

	FUZZ_LOOP(k, 2000)
	{
		char	**a;
		char	**b;
		size_t	i;

		rand_str(s, 40, "ab  ");
		INPUT("ft_split(%s, ' ')", zft_str(s));
		a = ft_split(s, ' ');
		b = r_split(s, ' ');
		CHECK(a != NULL, "a renvoyé NULL");
		for (i = 0; b[i]; i++)
		{
			CHECK(a[i] != NULL, "trop peu de mots (%zu au lieu de plus)", i);
			EQ_STR(a[i], b[i]);
		}
		CHECK(a[i] == NULL, "trop de mots (le tableau doit finir par NULL)");
		free_split(a);
		free_split(b);
	}
}
MTEST(ft_split, "chaque malloc échoue -> NULL et tout est libéré")
{
	char	**r;

	ARM();
	r = ft_split("  lorem ipsum dolor sit  amet ", ' ');
	DISARM();
	if (FAILING)
		CHECK(r == NULL, "doit renvoyer NULL si une allocation échoue (sujet)");
	free_split(r);
}
VS(ft_split, "s NULL")
{
	char	**r = PICK(ft_split, r_split)(NULL, ' ');

	out_split(r);
	free_split(r);
}

/* ============================================================ itoa ===== */
#define ITOA(n) do { int _v = (int)(n); char _e[16]; \
	snprintf(_e, 16, "%d", _v); INPUT("ft_itoa(%d)", _v); \
	char *_r = ft_itoa(_v); CHECK(_r != NULL, "a renvoyé NULL"); \
	EQ_STR(_r, _e); STR_ALLOC(_r); free(_r); } while (0)

TEST(ft_itoa, "0")               { ITOA(0); }
TEST(ft_itoa, "positifs")        { ITOA(1); ITOA(9); ITOA(10); ITOA(42); ITOA(100); ITOA(123456789); }
TEST(ft_itoa, "négatifs")        { ITOA(-1); ITOA(-9); ITOA(-10); ITOA(-42); ITOA(-100); }
TEST(ft_itoa, "INT_MAX")         { ITOA(INT_MAX); }
TEST(ft_itoa, "INT_MIN")         { ITOA(INT_MIN); }
FUZZ_TEST(ft_itoa, "aléatoire (5000 cas)")
{
	FUZZ_LOOP(k, 5000)
		ITOA((int)zrand() >> (zrand() % 31));
}
SPEC_TEST(ft_itoa, "taille exacte")
{
	int	v[] = {0, 7, -7, 1000, -1000, INT_MIN, INT_MAX};

	for (int i = 0; i < 7; i++)
	{
		char	*r = ft_itoa(v[i]);

		INPUT("ft_itoa(%d)", v[i]);
		CHECK(r != NULL, "a renvoyé NULL");
		EXACT_ALLOC(r);
		free(r);
	}
}
MTEST(ft_itoa, "malloc échoue -> NULL")
{
	char	*r;

	ARM();
	r = ft_itoa(-123);
	DISARM();
	if (FAILING)
		CHECK(r == NULL, "doit renvoyer NULL si malloc échoue");
	free(r);
}

/* ========================================================= strmapi ===== */
static char	f_upper(unsigned int i, char c) { (void)i; return ((char)toupper(c)); }
static char	f_idx(unsigned int i, char c) { return ((char)(c + (char)i)); }
static unsigned int	g_calls;
static char	f_count(unsigned int i, char c) { (void)i; g_calls++; return (c); }

TEST(ft_strmapi, "applique f")
{
	char	*r = ft_strmapi(gstr("hello"), f_upper);

	CHECK(r != NULL, "a renvoyé NULL");
	EQ_STR(r, "HELLO");
	STR_ALLOC(r);
	free(r);
}
TEST(ft_strmapi, "index passé à f (0, 1, 2, ...)")
{
	char	*r = ft_strmapi(gstr("aaaaa"), f_idx);

	CHECK(r != NULL, "a renvoyé NULL");
	EQ_STR(r, "abcde");
	free(r);
}
TEST(ft_strmapi, "f appelée strlen fois, s intacte")
{
	char	*s = gstr("12345678");
	char	*r;

	g_calls = 0;
	r = ft_strmapi(s, f_count);
	EQ_INT(g_calls, 8);
	EQ_STR(s, "12345678");
	CHECK(r != s, "doit renvoyer une nouvelle chaîne");
	free(r);
}
TEST(ft_strmapi, "chaîne vide")
{
	char	*r;

	g_calls = 0;
	r = ft_strmapi(gstr(""), f_count);
	CHECK(r != NULL, "a renvoyé NULL");
	EQ_STR(r, "");
	EQ_INT(g_calls, 0);
	free(r);
}
MTEST(ft_strmapi, "malloc échoue -> NULL")
{
	char	*r;

	ARM();
	r = ft_strmapi("abc", f_upper);
	DISARM();
	if (FAILING)
		CHECK(r == NULL, "doit renvoyer NULL si malloc échoue");
	free(r);
}
VS(ft_strmapi, "s NULL")
{
	char	*r = PICK(ft_strmapi, r_strmapi)(NULL, f_upper);

	OUT("%s", zft_str(r));
	free(r);
}
VS(ft_strmapi, "f NULL")
{
	char	*r = PICK(ft_strmapi, r_strmapi)("abc", NULL);

	OUT("%s", zft_str(r));
	free(r);
}

/* ======================================================== striteri ===== */
static void	fi_upper(unsigned int i, char *c) { (void)i; *c = (char)toupper(*c); }
static void	fi_idx(unsigned int i, char *c) { *c = (char)(*c + (char)i); }
static char	*g_base;
static int	g_bad_ptr;
static void	fi_ptr(unsigned int i, char *c) { if (c != g_base + i) g_bad_ptr = 1; }

TEST(ft_striteri, "modifie sur place")
{
	char	*s = gstr("hello");

	ft_striteri(s, fi_upper);
	EQ_STR(s, "HELLO");
}
TEST(ft_striteri, "index passé à f")
{
	char	*s = gstr("aaaa");

	ft_striteri(s, fi_idx);
	EQ_STR(s, "abcd");
}
TEST(ft_striteri, "f reçoit &s[i]")
{
	g_base = gstr("abcdef");
	g_bad_ptr = 0;
	ft_striteri(g_base, fi_ptr);
	CHECK(!g_bad_ptr, "f doit recevoir l'adresse du caractère dans s");
}
TEST(ft_striteri, "chaîne vide")
{
	ft_striteri(gstr(""), fi_upper);
}
VS(ft_striteri, "s NULL")
{
	PICK(ft_striteri, r_striteri)(NULL, fi_upper);
	OUT("ok");
}
VS(ft_striteri, "f NULL")
{
	char	s[] = "abc";

	PICK(ft_striteri, r_striteri)(s, NULL);
	OUT("%s", s);
}

/* ============================================================ put*_fd == */
TEST(ft_putchar_fd, "un caractère")
{
	int		fd = cap_open();
	size_t	l;

	ft_putchar_fd('a', fd);
	EQ_STR(cap_read(fd, &l), "a");
}
TEST(ft_putchar_fd, "les 256 valeurs")
{
	int					fd = cap_open();
	size_t				l;
	const unsigned char	*r;

	for (int c = 0; c < 256; c++)
		ft_putchar_fd((char)c, fd);
	r = (const unsigned char *)cap_read(fd, &l);
	EQ_SZ(l, 256);
	for (int c = 0; c < 256; c++)
		EQ_INT(r[c], c);
}
TEST(ft_putchar_fd, "fd invalide (-1) : pas de crash")
{
	ft_putchar_fd('x', -1);
}

TEST(ft_putstr_fd, "chaîne")
{
	int	fd = cap_open();

	ft_putstr_fd(gstr("Hello 42!"), fd);
	EQ_STR(cap_read(fd, NULL), "Hello 42!");
}
TEST(ft_putstr_fd, "chaîne vide")
{
	int		fd = cap_open();
	size_t	l;

	ft_putstr_fd(gstr(""), fd);
	cap_read(fd, &l);
	EQ_SZ(l, 0);
}
TEST(ft_putstr_fd, "longue chaîne (50 000)")
{
	int		fd = cap_open();
	char	*s = gbuf(50001, 'z');
	size_t	l;

	s[50000] = 0;
	ft_putstr_fd(s, fd);
	cap_read(fd, &l);
	EQ_SZ(l, 50000);
}
TEST(ft_putstr_fd, "fd invalide (-1) : pas de crash")
{
	ft_putstr_fd("abc", -1);
}
VS(ft_putstr_fd, "s NULL")
{
	int	fd = cap_open();

	PICK(ft_putstr_fd, r_putstr_fd)(NULL, fd);
	OUT("%s", zft_str(cap_read(fd, NULL)));
}

TEST(ft_putendl_fd, "chaîne + '\\n'")
{
	int	fd = cap_open();

	ft_putendl_fd(gstr("Hello"), fd);
	EQ_STR(cap_read(fd, NULL), "Hello\n");
}
TEST(ft_putendl_fd, "chaîne vide -> \"\\n\"")
{
	int	fd = cap_open();

	ft_putendl_fd(gstr(""), fd);
	EQ_STR(cap_read(fd, NULL), "\n");
}
TEST(ft_putendl_fd, "fd invalide (-1) : pas de crash")
{
	ft_putendl_fd("abc", -1);
}
VS(ft_putendl_fd, "s NULL")
{
	int	fd = cap_open();

	PICK(ft_putendl_fd, r_putendl_fd)(NULL, fd);
	OUT("%s", zft_str(cap_read(fd, NULL)));
}

#define PUTNBR(n) do { int _v = (int)(n); int _fd = cap_open(); char _e[16]; \
	snprintf(_e, 16, "%d", _v); INPUT("ft_putnbr_fd(%d, fd)", _v); \
	ft_putnbr_fd(_v, _fd); EQ_STR(cap_read(_fd, NULL), _e); close(_fd); \
	} while (0)

TEST(ft_putnbr_fd, "0, positifs, négatifs") { PUTNBR(0); PUTNBR(5); PUTNBR(42); PUTNBR(-42); PUTNBR(100); PUTNBR(-100); }
TEST(ft_putnbr_fd, "INT_MAX")               { PUTNBR(INT_MAX); }
TEST(ft_putnbr_fd, "INT_MIN")               { PUTNBR(INT_MIN); }
FUZZ_TEST(ft_putnbr_fd, "aléatoire (2000 cas)")
{
	FUZZ_LOOP(k, 2000)
		PUTNBR((int)zrand() >> (zrand() % 31));
}
TEST(ft_putnbr_fd, "fd invalide (-1) : pas de crash")
{
	ft_putnbr_fd(INT_MIN, -1);
	ft_putnbr_fd(42, -1);
}
