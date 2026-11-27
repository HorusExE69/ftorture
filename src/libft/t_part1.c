/* ************************************************************************** */
/*  PART 1 — libc functions. Compared to the real glibc (or BSD for strl*,    */
/*  strnstr). Guarded buffers turn every out-of-bounds read into a crash.     */
/* ************************************************************************** */
#include "zft.h"
#include "libft_decl.h"
#include "refs.h"

/* ================================================== is* (1 / 0 exactly) == */
#define IS_TESTS(NAME, REAL) \
TEST(ft_##NAME, "0..255 + EOF : renvoie exactement 1 ou 0") \
{ \
	for (int c = -1; c < 256; c++) \
	{ \
		INPUT("ft_" #NAME "(%d)", c); \
		EQ_INT(ft_##NAME(c), REAL(c) ? 1 : 0); \
	} \
} \
VS(ft_##NAME, "même vérité que la libc sur -128..255") \
{ \
	for (int c = -128; c < 256; c++) \
		OUT("%d", PICK(ft_##NAME, r_##NAME)(c) != 0); \
} \
SPEC_TEST(ft_##NAME, "hors unsigned char (INT_MIN, INT_MAX, 256+'a')") \
{ \
	int v[] = {INT_MIN, INT_MAX, 256 + 'a', 256 + '5', -1000, 1000}; \
	for (int i = 0; i < 6; i++) \
	{ \
		INPUT("ft_" #NAME "(%d)", v[i]); \
		EQ_INT(ft_##NAME(v[i]), 0); \
	} \
}

IS_TESTS(isalpha, isalpha)
IS_TESTS(isdigit, isdigit)
IS_TESTS(isalnum, isalnum)
IS_TESTS(isprint, isprint)

TEST(ft_isascii, "0..127 -> 1, le reste -> 0")
{
	for (int c = -300; c < 600; c++)
	{
		INPUT("ft_isascii(%d)", c);
		EQ_INT(ft_isascii(c), (c >= 0 && c <= 127) ? 1 : 0);
	}
}
TEST(ft_isascii, "INT_MIN / INT_MAX")
{
	EQ_INT(ft_isascii(INT_MIN), 0);
	EQ_INT(ft_isascii(INT_MAX), 0);
}
VS(ft_isascii, "même vérité que la libc")
{
	for (int c = -1000; c < 1000; c++)
		OUT("%d", PICK(ft_isascii, r_isascii)(c) != 0);
}

/* ========================================================== strlen ===== */
TEST(ft_strlen, "chaînes simples")
{
	EQ_SZ(ft_strlen(""), 0);
	EQ_SZ(ft_strlen("a"), 1);
	EQ_SZ(ft_strlen("Hello, World!"), 13);
	EQ_SZ(ft_strlen("abc\0def"), 3);
	EQ_SZ(ft_strlen("\n\t\v\r"), 4);
}
TEST(ft_strlen, "lecture pile jusqu'au '\\0' (buffer gardé)")
{
	EQ_SZ(ft_strlen(gstr("")), 0);
	EQ_SZ(ft_strlen(gstr("42 Paris")), 8);
}
TEST(ft_strlen, "caractères non-ASCII (char signé)")
{
	EQ_SZ(ft_strlen(gstr("\xff\x80\xe9\x01")), 4);
}
TEST(ft_strlen, "longue chaîne (100 000)")
{
	char	*s = gbuf(100001, 'x');

	s[100000] = 0;
	EQ_SZ(ft_strlen(s), 100000);
}
VS(ft_strlen, "NULL")
{
	OUT("%zu", PICK(ft_strlen, r_strlen)(NULL));
}

/* ========================================================== memset ===== */
TEST(ft_memset, "remplit et renvoie s")
{
	char	a[32], b[32];

	memset(a, 'z', 32);
	memset(b, 'z', 32);
	EQ_PTR(ft_memset(a, 'A', 10), a);
	memset(b, 'A', 10);
	EQ_MEM(a, b, 32);
}
TEST(ft_memset, "c > 255 converti en unsigned char")
{
	unsigned char	a[8];

	ft_memset(a, 0x141, 8);
	for (int i = 0; i < 8; i++)
		EQ_INT(a[i], 0x41);
	ft_memset(a, -1, 8);
	for (int i = 0; i < 8; i++)
		EQ_INT(a[i], 0xff);
}
TEST(ft_memset, "n = 0 ne touche à rien")
{
	char	*a = gbuf(4, 'q');

	ft_memset(a, 'X', 0);
	EQ_MEM(a, "qqqq", 4);
	ft_memset(a + 4, 'X', 0);
}
TEST(ft_memset, "exactement n octets (buffer gardé)")
{
	char	*a = gbuf(100, 0);

	ft_memset(a, 'k', 100);
	for (int i = 0; i < 100; i++)
		EQ_INT(a[i], 'k');
}
VS(ft_memset, "NULL avec n = 0")
{
	void	*r = PICK(ft_memset, r_memset)(NULL, 'a', 0);

	OUT("%s", r ? "non-NULL" : "NULL");
}
VS(ft_memset, "NULL avec n = 5")
{
	PICK(ft_memset, r_memset)(NULL, 'a', 5);
	OUT("pas de crash");
}

/* =========================================================== bzero ===== */
TEST(ft_bzero, "met à zéro n octets exactement")
{
	char	a[16];

	memset(a, 'x', 16);
	ft_bzero(a + 2, 5);
	for (int i = 0; i < 16; i++)
		EQ_INT(a[i], (i >= 2 && i < 7) ? 0 : 'x');
}
TEST(ft_bzero, "n = 0")
{
	char	*a = gbuf(3, 'x');

	ft_bzero(a, 0);
	EQ_MEM(a, "xxx", 3);
	ft_bzero(a + 3, 0);
}
TEST(ft_bzero, "buffer gardé")
{
	char	*a = gbuf(64, 'x');

	ft_bzero(a, 64);
	for (int i = 0; i < 64; i++)
		EQ_INT(a[i], 0);
}
VS(ft_bzero, "NULL avec n = 0")
{
	PICK(ft_bzero, r_bzero)(NULL, 0);
	OUT("ok");
}
VS(ft_bzero, "NULL avec n = 3")
{
	PICK(ft_bzero, r_bzero)(NULL, 3);
	OUT("ok");
}

/* ========================================================== memcpy ===== */
TEST(ft_memcpy, "copie et renvoie dest")
{
	char	d[16];
	char	*s = gmem("Hello\0World", 12);

	memset(d, 'z', 16);
	EQ_PTR(ft_memcpy(d, s, 12), d);
	EQ_MEM(d, "Hello\0World\0zzzz", 16);
}
TEST(ft_memcpy, "n = 0")
{
	char	d[4] = "abc";

	EQ_PTR(ft_memcpy(d, "xyz", 0), d);
	EQ_STR(d, "abc");
}
TEST(ft_memcpy, "ne lit/écrit pas au-delà de n (gardé)")
{
	char	*s = gmem("0123456789", 10);
	char	*d = gbuf(10, 0);

	ft_memcpy(d, s, 10);
	EQ_MEM(d, "0123456789", 10);
}
TEST(ft_memcpy, "octets > 127 et grands buffers")
{
	unsigned char	*s = gbuf(4096, 0);
	unsigned char	*d = gbuf(4096, 0);

	for (int i = 0; i < 4096; i++)
		s[i] = (unsigned char)(zrand());
	ft_memcpy(d, s, 4096);
	EQ_MEM(d, s, 4096);
}
VS(ft_memcpy, "dest et src NULL, n = 0")
{
	void	*r = PICK(ft_memcpy, r_memcpy)(NULL, NULL, 0);

	OUT("%s", r ? "non-NULL" : "NULL");
}
VS(ft_memcpy, "dest et src NULL, n = 3")
{
	void	*r = PICK(ft_memcpy, r_memcpy)(NULL, NULL, 3);

	OUT("%s", r ? "non-NULL" : "NULL");
}
VS(ft_memcpy, "dest NULL, n = 3")
{
	PICK(ft_memcpy, r_memcpy)(NULL, "abc", 3);
	OUT("ok");
}
VS(ft_memcpy, "src NULL, n = 3")
{
	char	d[4];

	PICK(ft_memcpy, r_memcpy)(d, NULL, 3);
	OUT("ok");
}

/* ========================================================= memmove ===== */
TEST(ft_memmove, "sans chevauchement")
{
	char	d[8] = {0};

	EQ_PTR(ft_memmove(d, "abcdef", 7), d);
	EQ_STR(d, "abcdef");
}
TEST(ft_memmove, "chevauchement dest > src")
{
	char	b[] = "0123456789";

	ft_memmove(b + 2, b, 6);
	EQ_STR(b, "0101234589");
}
TEST(ft_memmove, "chevauchement dest < src")
{
	char	b[] = "0123456789";

	ft_memmove(b, b + 3, 6);
	EQ_STR(b, "3456786789");
}
TEST(ft_memmove, "dest == src")
{
	char	b[] = "same";

	EQ_PTR(ft_memmove(b, b, 4), b);
	EQ_STR(b, "same");
}
TEST(ft_memmove, "n = 0")
{
	char	b[] = "abc";

	ft_memmove(b, "zzz", 0);
	EQ_STR(b, "abc");
}
TEST(ft_memmove, "chevauchement aux bords des buffers gardés")
{
	char	*b = gbuf(64, 0);

	for (int i = 0; i < 64; i++)
		b[i] = (char)i;
	ft_memmove(b + 1, b, 63);
	for (int i = 1; i < 64; i++)
		EQ_INT(b[i], i - 1);
	ft_memmove(b, b + 1, 63);
	for (int i = 0; i < 63; i++)
		EQ_INT(b[i], i);
}
FUZZ_TEST(ft_memmove, "aléatoire vs memmove (2000 cas)")
{
	char	a[300];
	char	b[300];

	FUZZ_LOOP(k, 2000)
	{
		size_t	n = zrand() % 120;
		size_t	s = zrand() % 150;
		size_t	d = zrand() % 150;

		for (int i = 0; i < 300; i++)
			a[i] = b[i] = (char)zrand();
		INPUT("ft_memmove(buf+%zu, buf+%zu, %zu)", d, s, n);
		ft_memmove(a + d, a + s, n);
		memmove(b + d, b + s, n);
		EQ_MEM(a, b, 300);
	}
}
VS(ft_memmove, "dest et src NULL, n = 0")
{
	void	*r = PICK(ft_memmove, r_memmove)(NULL, NULL, 0);

	OUT("%s", r ? "non-NULL" : "NULL");
}
VS(ft_memmove, "dest et src NULL, n = 5")
{
	void	*r = PICK(ft_memmove, r_memmove)(NULL, NULL, 5);

	OUT("%s", r ? "non-NULL" : "NULL");
}

/* ========================================================= strlcpy ===== */
#define LCPY(dsz, src, size) do { \
	char *_s = gstr(src); \
	char _a[64], _b[64]; \
	memset(_a, 'Z', 64); memset(_b, 'Z', 64); \
	INPUT("ft_strlcpy(dst[%d], %s, %d)", dsz, zft_str(src), size); \
	size_t _r1 = ft_strlcpy(_a, _s, size); \
	size_t _r2 = r_strlcpy(_b, _s, size); \
	EQ_SZ(_r1, _r2); \
	EQ_MEM(_a, _b, dsz); \
	} while (0)

TEST(ft_strlcpy, "copie complète")             { LCPY(16, "hello", 16); }
TEST(ft_strlcpy, "troncature")                 { LCPY(16, "hello world", 6); }
TEST(ft_strlcpy, "size = 1 -> juste '\\0'")    { LCPY(8, "hello", 1); }
TEST(ft_strlcpy, "size = 0 -> n'écrit rien")   { LCPY(8, "hello", 0); }
TEST(ft_strlcpy, "src vide")                   { LCPY(8, "", 8); }
TEST(ft_strlcpy, "size == strlen(src)")        { LCPY(8, "abcd", 4); }
TEST(ft_strlcpy, "size == strlen(src) + 1")    { LCPY(8, "abcd", 5); }
TEST(ft_strlcpy, "dst gardé, size exact")
{
	char	*d = gbuf(6, 'x');

	EQ_SZ(ft_strlcpy(d, "hello world", 6), 11);
	EQ_STR(d, "hello");
}
FUZZ_TEST(ft_strlcpy, "aléatoire vs BSD (2000 cas)")
{
	char	src[80];
	char	a[80];
	char	b[80];

	FUZZ_LOOP(k, 2000)
	{
		size_t	l = zrand() % 70;
		size_t	sz = zrand() % 75;

		for (size_t i = 0; i < l; i++)
			src[i] = (char)(' ' + zrand() % 90);
		src[l] = 0;
		memset(a, 'Z', 80);
		memset(b, 'Z', 80);
		INPUT("ft_strlcpy(dst, %s, %zu)", zft_str(src), sz);
		EQ_SZ(ft_strlcpy(a, src, sz), r_strlcpy(b, src, sz));
		EQ_MEM(a, b, 80);
	}
}
VS(ft_strlcpy, "dst NULL, size = 0")
{
	OUT("%zu", PICK(ft_strlcpy, r_strlcpy)(NULL, "abc", 0));
}
VS(ft_strlcpy, "src NULL")
{
	char	d[8];

	OUT("%zu", PICK(ft_strlcpy, r_strlcpy)(d, NULL, 8));
}
VS(ft_strlcpy, "dst NULL, size = 5")
{
	OUT("%zu", PICK(ft_strlcpy, r_strlcpy)(NULL, "abc", 5));
}

/* ========================================================= strlcat ===== */
#define LCAT(dst0, src, size) do { \
	char _a[64], _b[64]; \
	memset(_a, 'Z', 64); memset(_b, 'Z', 64); \
	strcpy(_a, dst0); strcpy(_b, dst0); \
	INPUT("ft_strlcat(%s, %s, %d)", zft_str(dst0), zft_str(src), size); \
	size_t _r1 = ft_strlcat(_a, gstr(src), size); \
	size_t _r2 = r_strlcat(_b, src, size); \
	EQ_SZ(_r1, _r2); \
	EQ_MEM(_a, _b, 64); \
	} while (0)

TEST(ft_strlcat, "concat simple")              { LCAT("Hello, ", "World", 20); }
TEST(ft_strlcat, "dst vide")                   { LCAT("", "Data", 20); }
TEST(ft_strlcat, "src vide")                   { LCAT("Hello", "", 20); }
TEST(ft_strlcat, "troncature")                 { LCAT("Hello, ", "World!", 10); }
TEST(ft_strlcat, "pile la place")              { LCAT("Hello, ", "World!", 14); }
TEST(ft_strlcat, "pas de place (size = dstlen+1)") { LCAT("Hello", "World", 6); }
TEST(ft_strlcat, "size < strlen(dst)")         { LCAT("ABCDEFGHI", "12345", 5); }
TEST(ft_strlcat, "size = strlen(dst)")         { LCAT("ABCDE", "123", 5); }
TEST(ft_strlcat, "size = 0")                   { LCAT("abc", "def", 0); }
TEST(ft_strlcat, "dst non terminé dans size : ne lit pas au-delà")
{
	char	*d = gmem("abcd", 4);

	INPUT("ft_strlcat(\"abcd\"(sans \\0, 4 octets gardés), \"xyz\", 4)");
	EQ_SZ(ft_strlcat(d, "xyz", 4), 7);
	EQ_MEM(d, "abcd", 4);
}
FUZZ_TEST(ft_strlcat, "aléatoire vs BSD (2000 cas)")
{
	char	src[40];
	char	a[90];
	char	b[90];

	FUZZ_LOOP(k, 2000)
	{
		size_t	ls = zrand() % 35;
		size_t	ld = zrand() % 40;
		size_t	sz = zrand() % 85;

		for (size_t i = 0; i < ls; i++)
			src[i] = (char)('a' + zrand() % 26);
		src[ls] = 0;
		memset(a, 'Z', 90);
		memset(a, 'd', ld);
		a[ld] = 0;
		memcpy(b, a, 90);
		INPUT("ft_strlcat(%s, %s, %zu)", zft_str(a), zft_str(src), sz);
		EQ_SZ(ft_strlcat(a, src, sz), r_strlcat(b, src, sz));
		EQ_MEM(a, b, 90);
	}
}
VS(ft_strlcat, "dst NULL, size = 0")
{
	OUT("%zu", PICK(ft_strlcat, r_strlcat)(NULL, "abc", 0));
}
VS(ft_strlcat, "src NULL")
{
	char	d[8] = "ab";

	OUT("%zu", PICK(ft_strlcat, r_strlcat)(d, NULL, 8));
}
VS(ft_strlcat, "dst NULL, size = 5")
{
	OUT("%zu", PICK(ft_strlcat, r_strlcat)(NULL, "abc", 5));
}

/* ================================================= toupper / tolower ==== */
TEST(ft_toupper, "EOF..255 identique à la libc")
{
	for (int c = -1; c < 256; c++)
	{
		INPUT("ft_toupper(%d)", c);
		EQ_INT(ft_toupper(c), toupper(c));
	}
}
/* not compared to glibc here: its toupper(-128..-2) returns 128..254 (table
   quirk), so every normal implementation would get a ▲ for nothing.      */
SPEC_TEST(ft_toupper, "hors unsigned char : renvoie c inchangé")
{
	int	v[] = {INT_MIN, -1000, -129, -128, -2, 256, 256 + 'a', 256 + 'A',
		1000, INT_MAX};

	for (int i = 0; i < 10; i++)
	{
		INPUT("ft_toupper(%d)", v[i]);
		EQ_INT(ft_toupper(v[i]), v[i]);
	}
}
TEST(ft_tolower, "EOF..255 identique à la libc")
{
	for (int c = -1; c < 256; c++)
	{
		INPUT("ft_tolower(%d)", c);
		EQ_INT(ft_tolower(c), tolower(c));
	}
}
/* not compared to glibc here: its tolower(-128..-2) returns 128..254 (table
   quirk), so every normal implementation would get a ▲ for nothing.      */
SPEC_TEST(ft_tolower, "hors unsigned char : renvoie c inchangé")
{
	int	v[] = {INT_MIN, -1000, -129, -128, -2, 256, 256 + 'a', 256 + 'A',
		1000, INT_MAX};

	for (int i = 0; i < 10; i++)
	{
		INPUT("ft_tolower(%d)", v[i]);
		EQ_INT(ft_tolower(v[i]), v[i]);
	}
}

/* ================================================= strchr / strrchr ===== */
static long	ptr_off(const char *r, const char *base)
{
	return (r ? (long)(r - base) : -1L);
}
#define PTR_OUT(r, base) ptr_off((r), (base))

#define CHR_TESTS(NAME) \
TEST(ft_##NAME, "trouvé / pas trouvé / premier ou dernier") \
{ \
	const char *s = gstr("teste-moi bien"); \
	const char *t[] = {"t", "e", "-", "n", "z", " "}; \
	for (int i = 0; i < 6; i++) \
	{ \
		INPUT("ft_" #NAME "(\"teste-moi bien\", '%s')", t[i]); \
		EQ_PTR(ft_##NAME(s, t[i][0]), r_##NAME(s, t[i][0])); \
	} \
} \
TEST(ft_##NAME, "c = '\\0' -> pointe sur le terminateur") \
{ \
	const char *s = gstr("abc"); \
	EQ_PTR(ft_##NAME(s, 0), s + 3); \
	s = gstr(""); \
	EQ_PTR(ft_##NAME(s, 0), s); \
} \
TEST(ft_##NAME, "c converti en char ('a' + 256, -256 + 'e')") \
{ \
	const char *s = gstr("bonjour tes"); \
	EQ_PTR(ft_##NAME(s, 's' + 256), r_##NAME(s, 's' + 256)); \
	EQ_PTR(ft_##NAME(s, 'e' - 256), r_##NAME(s, 'e' - 256)); \
	EQ_PTR(ft_##NAME(s, 256), r_##NAME(s, 256)); \
} \
TEST(ft_##NAME, "caractères > 127") \
{ \
	const char *s = gstr("caf\xe9 cr\xe8me \xe9t\xe9"); \
	EQ_PTR(ft_##NAME(s, 0xe9), r_##NAME(s, 0xe9)); \
	EQ_PTR(ft_##NAME(s, (char)0xe8), r_##NAME(s, (char)0xe8)); \
} \
TEST(ft_##NAME, "chaîne vide, ne lit pas après le '\\0'") \
{ \
	const char *s = gstr(""); \
	EQ_PTR(ft_##NAME(s, 'a'), NULL); \
	s = gstr("xyz"); \
	EQ_PTR(ft_##NAME(s, 'q'), NULL); \
} \
VS(ft_##NAME, "NULL") \
{ \
	char *r = PICK(ft_##NAME, r_##NAME)(NULL, 'a'); \
	OUT("%s", r ? "non-NULL" : "NULL"); \
}

CHR_TESTS(strchr)
CHR_TESTS(strrchr)

/* ========================================================= strncmp ===== */
TEST(ft_strncmp, "égal / différent / n limité")
{
	EQ_INT(SIGN(ft_strncmp("abc", "abc", 3)), 0);
	EQ_INT(SIGN(ft_strncmp("abc", "abd", 3)), -1);
	EQ_INT(SIGN(ft_strncmp("abd", "abc", 3)), 1);
	EQ_INT(SIGN(ft_strncmp("abcX", "abcY", 3)), 0);
	EQ_INT(SIGN(ft_strncmp("abc", "abcdef", 3)), 0);
	EQ_INT(SIGN(ft_strncmp("abc", "abcdef", 6)), -1);
	EQ_INT(SIGN(ft_strncmp("abcdef", "abc", 6)), 1);
}
TEST(ft_strncmp, "n = 0")
{
	EQ_INT(ft_strncmp("abc", "xyz", 0), 0);
	EQ_INT(ft_strncmp(gstr(""), gstr("z"), 0), 0);
}
TEST(ft_strncmp, "comparaison en unsigned char (\\200 > \\0)")
{
	EQ_INT(SIGN(ft_strncmp("\200", "\0", 1)), 1);
	EQ_INT(SIGN(ft_strncmp("a\xff", "a\x01", 2)), 1);
	EQ_INT(SIGN(ft_strncmp("\x01", "\xfe", 1)), -1);
}
TEST(ft_strncmp, "s'arrête au '\\0' même si n est grand (gardé)")
{
	EQ_INT(SIGN(ft_strncmp(gstr("abc"), gstr("abc"), 1000)), 0);
	EQ_INT(SIGN(ft_strncmp(gstr("ab"), gstr("abc"), 1000)), -1);
	EQ_INT(SIGN(ft_strncmp(gstr("test\0abc"), gstr("test\0xyz"), 9)), 0);
}
TEST(ft_strncmp, "ne lit pas plus de n octets (gardé)")
{
	char	*a = gmem("abcd", 4);
	char	*b = gmem("abcd", 4);

	EQ_INT(ft_strncmp(a, b, 4), 0);
}
FUZZ_TEST(ft_strncmp, "aléatoire vs libc, signe (5000 cas)")
{
	char	a[32];
	char	b[32];

	FUZZ_LOOP(k, 5000)
	{
		size_t	la = zrand() % 20;
		size_t	lb = zrand() % 20;
		size_t	n = zrand() % 25;

		for (size_t i = 0; i < la; i++)
			a[i] = (char)("abc\x80\xff"[zrand() % 5]);
		for (size_t i = 0; i < lb; i++)
			b[i] = (char)("abc\x80\xff"[zrand() % 5]);
		a[la] = 0;
		b[lb] = 0;
		INPUT("ft_strncmp(%s, %s, %zu)", zft_str(a), zft_str(b), n);
		EQ_INT(SIGN(ft_strncmp(a, b, n)), SIGN(strncmp(a, b, n)));
	}
}
VS(ft_strncmp, "NULL, n = 0")
{
	OUT("%d", SIGN(PICK(ft_strncmp, r_strncmp)(NULL, NULL, 0)));
}
VS(ft_strncmp, "s1 NULL, n = 3")
{
	OUT("%d", SIGN(PICK(ft_strncmp, r_strncmp)(NULL, "abc", 3)));
}
VS(ft_strncmp, "s2 NULL, n = 3")
{
	OUT("%d", SIGN(PICK(ft_strncmp, r_strncmp)("abc", NULL, 3)));
}

/* ========================================================== memchr ===== */
TEST(ft_memchr, "trouvé / pas trouvé")
{
	const char	*s = gmem("bonjour", 7);

	EQ_PTR(ft_memchr(s, 'j', 7), s + 3);
	EQ_PTR(ft_memchr(s, 'b', 7), s);
	EQ_PTR(ft_memchr(s, 'r', 7), s + 6);
	EQ_PTR(ft_memchr(s, 'z', 7), NULL);
	EQ_PTR(ft_memchr(s, 'r', 6), NULL);
}
TEST(ft_memchr, "ne s'arrête pas au '\\0'")
{
	const char	*s = gmem("ab\0cd", 5);

	EQ_PTR(ft_memchr(s, 'd', 5), s + 4);
	EQ_PTR(ft_memchr(s, 0, 5), s + 2);
}
TEST(ft_memchr, "c converti en unsigned char")
{
	const unsigned char	s[] = {1, 2, 0xde, 0x41, 0};
	const void			*g = gmem(s, 5);

	EQ_PTR(ft_memchr(g, 0xde, 5), (const char *)g + 2);
	EQ_PTR(ft_memchr(g, 0xde - 256, 5), (const char *)g + 2);
	EQ_PTR(ft_memchr(g, 0x141, 5), (const char *)g + 3);
}
TEST(ft_memchr, "n = 0")
{
	EQ_PTR(ft_memchr(gmem("a", 1), 'a', 0), NULL);
}
VS(ft_memchr, "NULL, n = 0")
{
	void	*r = PICK(ft_memchr, r_memchr)(NULL, 'a', 0);

	OUT("%s", r ? "non-NULL" : "NULL");
}
VS(ft_memchr, "NULL, n = 4")
{
	void	*r = PICK(ft_memchr, r_memchr)(NULL, 'a', 4);

	OUT("%s", r ? "non-NULL" : "NULL");
}

/* ========================================================== memcmp ===== */
TEST(ft_memcmp, "égal / différent")
{
	EQ_INT(SIGN(ft_memcmp("abc", "abc", 3)), 0);
	EQ_INT(SIGN(ft_memcmp("abc", "abd", 3)), -1);
	EQ_INT(SIGN(ft_memcmp("abd", "abc", 3)), 1);
	EQ_INT(SIGN(ft_memcmp("abc", "abd", 2)), 0);
}
TEST(ft_memcmp, "ne s'arrête pas au '\\0'")
{
	EQ_INT(SIGN(ft_memcmp("ab\0c", "ab\0d", 4)), -1);
	EQ_INT(SIGN(ft_memcmp("\0\0\0a", "\0\0\0a", 4)), 0);
}
TEST(ft_memcmp, "unsigned char (\\200 > \\0)")
{
	EQ_INT(SIGN(ft_memcmp("\200", "\0", 1)), 1);
	EQ_INT(SIGN(ft_memcmp("\x01", "\xff", 1)), -1);
}
TEST(ft_memcmp, "n = 0 et lecture bornée (gardé)")
{
	EQ_INT(ft_memcmp("a", "b", 0), 0);
	EQ_INT(ft_memcmp(gmem("xyz", 3), gmem("xyz", 3), 3), 0);
}
FUZZ_TEST(ft_memcmp, "aléatoire vs libc, signe (5000 cas)")
{
	unsigned char	a[24];
	unsigned char	b[24];

	FUZZ_LOOP(k, 5000)
	{
		size_t	n = zrand() % 24;

		for (int i = 0; i < 24; i++)
		{
			a[i] = (unsigned char)(zrand() % 3 ? 'x' : zrand());
			b[i] = (unsigned char)(zrand() % 3 ? 'x' : zrand());
		}
		INPUT("ft_memcmp(%s, %s, %zu)", zft_mem(a, n), zft_mem(b, n), n);
		EQ_INT(SIGN(ft_memcmp(a, b, n)), SIGN(memcmp(a, b, n)));
	}
}
VS(ft_memcmp, "NULL, n = 0")
{
	OUT("%d", SIGN(PICK(ft_memcmp, r_memcmp)(NULL, NULL, 0)));
}
VS(ft_memcmp, "NULL, n = 2")
{
	OUT("%d", SIGN(PICK(ft_memcmp, r_memcmp)(NULL, "ab", 2)));
}

/* ========================================================= strnstr ===== */
#define NSTR(big, little, len) do { \
	const char *_b = gstr(big); \
	INPUT("ft_strnstr(%s, %s, %zu)", zft_str(big), zft_str(little), \
		(size_t)(len)); \
	EQ_INT(PTR_OUT(ft_strnstr(_b, gstr(little), len), _b), \
		PTR_OUT(r_strnstr(_b, little, len), _b)); \
	} while (0)

TEST(ft_strnstr, "trouvé")                      { NSTR("Foo Bar Baz", "Bar", 11); }
TEST(ft_strnstr, "pas trouvé")                  { NSTR("Foo Bar Baz", "Qux", 11); }
TEST(ft_strnstr, "little vide -> big")          { NSTR("Foo", "", 3); NSTR("", "", 0); }
TEST(ft_strnstr, "len trop court")              { NSTR("Foo Bar Baz", "Bar", 6); }
TEST(ft_strnstr, "len pile")                    { NSTR("Foo Bar Baz", "Bar", 7); }
TEST(ft_strnstr, "len = 0")                     { NSTR("abc", "a", 0); }
TEST(ft_strnstr, "len > strlen(big)")           { NSTR("abc", "c", 1000); NSTR("abc", "abcd", 1000); }
TEST(ft_strnstr, "faux départ (aaab / aab)")    { NSTR("aaab", "aab", 4); NSTR("lorem ipsum", "ipsumm", 30); }
TEST(ft_strnstr, "little == big")               { NSTR("abc", "abc", 3); NSTR("abc", "abc", 2); }
TEST(ft_strnstr, "big non terminé dans len : lecture bornée")
{
	const char	*b = gmem("abcde", 5);

	INPUT("ft_strnstr(\"abcde\"(5 octets sans \\0, gardé), \"xyz\", 5)");
	EQ_PTR(ft_strnstr(b, "xyz", 5), NULL);
	EQ_PTR(ft_strnstr(b, "de", 5), b + 3);
}
FUZZ_TEST(ft_strnstr, "aléatoire vs BSD (3000 cas)")
{
	char	big[24];
	char	lit[6];

	FUZZ_LOOP(k, 3000)
	{
		size_t	lb = zrand() % 20;
		size_t	ll = zrand() % 5;
		size_t	len = zrand() % 25;

		for (size_t i = 0; i < lb; i++)
			big[i] = (char)('a' + zrand() % 3);
		for (size_t i = 0; i < ll; i++)
			lit[i] = (char)('a' + zrand() % 3);
		big[lb] = 0;
		lit[ll] = 0;
		INPUT("ft_strnstr(%s, %s, %zu)", zft_str(big), zft_str(lit), len);
		EQ_INT(PTR_OUT(ft_strnstr(big, lit, len), big),
			PTR_OUT(r_strnstr(big, lit, len), big));
	}
}
VS(ft_strnstr, "big NULL, len = 0")
{
	char	*r = PICK(ft_strnstr, r_strnstr)(NULL, "a", 0);

	OUT("%s", r ? "non-NULL" : "NULL");
}
VS(ft_strnstr, "big NULL, len = 5")
{
	char	*r = PICK(ft_strnstr, r_strnstr)(NULL, "a", 5);

	OUT("%s", r ? "non-NULL" : "NULL");
}
VS(ft_strnstr, "little NULL")
{
	char	*r = PICK(ft_strnstr, r_strnstr)("abc", NULL, 3);

	OUT("%s", r ? "non-NULL" : "NULL");
}

/* ============================================================ atoi ===== */
#define ATOI(s) do { INPUT("ft_atoi(%s)", zft_str(s)); \
	EQ_INT(ft_atoi(gstr(s)), atoi(s)); } while (0)

TEST(ft_atoi, "nombres simples")       { ATOI("0"); ATOI("42"); ATOI("-42"); ATOI("+42"); ATOI("007"); }
TEST(ft_atoi, "espaces isspace")       { ATOI(" \t\n\v\f\r 123"); ATOI("   -8"); }
TEST(ft_atoi, "signes multiples")      { ATOI("+-5"); ATOI("-+5"); ATOI("--5"); ATOI("++5"); ATOI("- 5"); }
TEST(ft_atoi, "s'arrête au premier non-chiffre") { ATOI("12ab34"); ATOI("12 34"); ATOI("1-2"); }
TEST(ft_atoi, "pas de chiffre")        { ATOI(""); ATOI("abc"); ATOI("-"); ATOI("+"); ATOI(" "); }
TEST(ft_atoi, "INT_MAX / INT_MIN")     { ATOI("2147483647"); ATOI("-2147483648"); ATOI("+2147483647"); }
TEST(ft_atoi, "espace non-isspace avant (\\x1c, \\b)") { ATOI("\x1c" "5"); ATOI("\b5"); ATOI("\0335"); }
FUZZ_TEST(ft_atoi, "aléatoire vs libc dans [INT_MIN, INT_MAX] (5000 cas)")
{
	char	buf[40];

	FUZZ_LOOP(k, 5000)
	{
		int	v = (int)zrand();

		snprintf(buf, sizeof(buf), "%s%s%d%s", zrand() % 2 ? "  " : "",
			zrand() % 4 == 0 && v >= 0 ? "+" : "", v, zrand() % 2 ? "x9" : "");
		ATOI(buf);
	}
}
VS_SPEC(ft_atoi, "dépassement (> INT_MAX, > LONG_MAX)")
{
	const char	*t[] = {"2147483648", "-2147483649", "4294967296",
		"9223372036854775807", "9223372036854775808", "-9223372036854775809",
		"99999999999999999999", "00000000000000000000000042"};

	for (int i = 0; i < 8; i++)
		OUT("%d", PICK(ft_atoi, r_atoi)(t[i]));
}
VS(ft_atoi, "NULL")
{
	OUT("%d", PICK(ft_atoi, r_atoi)(NULL));
}

/* ========================================================== calloc ===== */
TEST(ft_calloc, "mémoire mise à zéro, taille nmemb*size")
{
	unsigned char	*p = ft_calloc(10, 4);

	CHECK(p != NULL, "ft_calloc(10, 4) a renvoyé NULL");
	CHECK(alloc_size(p) != (size_t)-1 && alloc_size(p) >= 40,
		"bloc trop petit ou pas alloué par malloc (%zu octets pour 40)",
		alloc_size(p));
	for (int i = 0; i < 40; i++)
		EQ_INT(p[i], 0);
	free(p);
}
TEST(ft_calloc, "grand bloc mis à zéro")
{
	unsigned char	*p = ft_calloc(1, 100000);

	CHECK(p != NULL, "ft_calloc(1, 100000) a renvoyé NULL");
	for (int i = 0; i < 100000; i++)
		EQ_INT(p[i], 0);
	free(p);
}
TEST(ft_calloc, "(0, 0) -> pointeur unique libérable (règle du sujet)")
{
	void	*a = ft_calloc(0, 0);
	void	*b = ft_calloc(0, 0);

	CHECK(a != NULL, "ft_calloc(0, 0) doit renvoyer un pointeur non NULL");
	CHECK(b != NULL, "ft_calloc(0, 0) doit renvoyer un pointeur non NULL");
	CHECK(a != b, "deux appels ft_calloc(0, 0) doivent renvoyer des "
		"pointeurs différents");
	free(a);
	free(b);
}
TEST(ft_calloc, "(0, 5) et (5, 0) -> pointeur libérable")
{
	void	*a = ft_calloc(0, 5);
	void	*b = ft_calloc(5, 0);

	CHECK(a != NULL, "ft_calloc(0, 5) doit renvoyer un pointeur non NULL");
	CHECK(b != NULL, "ft_calloc(5, 0) doit renvoyer un pointeur non NULL");
	CHECK(alloc_size(a) != (size_t)-1, "le pointeur ne vient pas de malloc");
	free(a);
	free(b);
}
TEST(ft_calloc, "utilise malloc (pointeur libérable par free)")
{
	void	*p = ft_calloc(3, 3);

	CHECK(alloc_size(p) != (size_t)-1,
		"le pointeur renvoyé n'est pas le début d'un bloc malloc");
	free(p);
}
MTEST(ft_calloc, "malloc échoue -> NULL")
{
	void	*p;

	ARM();
	p = ft_calloc(4, 8);
	DISARM();
	if (FAILING)
		CHECK(p == NULL, "doit renvoyer NULL si malloc échoue");
	free(p);
}
VS_SPEC(ft_calloc, "dépassement nmemb * size (SIZE_MAX, 2)")
{
	void	*p = PICK(ft_calloc, r_calloc)(SIZE_MAX, 2);

	OUT("%s", p ? "non-NULL" : "NULL");
	XFREE(p);
}
VS_SPEC(ft_calloc, "dépassement (SIZE_MAX/2+2, 2) et (INT_MAX, INT_MAX)")
{
	void	*p = PICK(ft_calloc, r_calloc)(SIZE_MAX / 2 + 2, 2);
	void	*q;

	OUT("%s", p ? "non-NULL" : "NULL");
	XFREE(p);
	q = PICK(ft_calloc, r_calloc)((size_t)INT_MAX * 8, (size_t)INT_MAX * 8);
	OUT("%s", q ? "non-NULL" : "NULL");
	XFREE(q);
}

/* ========================================================== strdup ===== */
TEST(ft_strdup, "copie exacte, nouvelle zone")
{
	const char	*s = gstr("coucou 42");
	char		*d = ft_strdup(s);

	CHECK(d != NULL, "ft_strdup a renvoyé NULL");
	CHECK(d != s, "ft_strdup doit renvoyer une nouvelle zone mémoire");
	EQ_STR(d, "coucou 42");
	CHECK(alloc_size(d) != (size_t)-1 && alloc_size(d) >= 10,
		"bloc trop petit ou pas alloué par malloc (%zu octets pour 10)",
		alloc_size(d));
	free(d);
}
TEST(ft_strdup, "chaîne vide")
{
	char	*d = ft_strdup(gstr(""));

	CHECK(d != NULL, "ft_strdup(\"\") a renvoyé NULL");
	EQ_STR(d, "");
	CHECK(alloc_size(d) >= 1, "il faut allouer au moins 1 octet");
	free(d);
}
TEST(ft_strdup, "caractères non-ASCII et longue chaîne")
{
	char	*s = gbuf(5001, '\xe9');
	char	*d;

	s[5000] = 0;
	d = ft_strdup(s);
	CHECK(d != NULL, "ft_strdup a renvoyé NULL");
	EQ_SZ(strlen(d), 5000);
	EQ_MEM(d, s, 5001);
	free(d);
}
MTEST(ft_strdup, "malloc échoue -> NULL")
{
	char	*d;

	ARM();
	d = ft_strdup("hello");
	DISARM();
	if (FAILING)
		CHECK(d == NULL, "doit renvoyer NULL si malloc échoue");
	free(d);
}
VS(ft_strdup, "NULL")
{
	char	*d = PICK(ft_strdup, r_strdup)(NULL);

	OUT("%s", d ? "non-NULL" : "NULL");
	XFREE(d);
}
