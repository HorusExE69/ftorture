/* ************************************************************************** */
/*  ft_printf — MANDATORY PART (subject v12.1): cspdiuxX%                     */
/*  Every PF() compares output bytes and return value with the real printf.  */
/* ************************************************************************** */
#include "pf.h"

/* ================================================================= %c == */
TEST(pf_c, "caractères simples")      { PF("%c", 'a'); PF("%c", '0'); PF("%c", ' '); PF("%c", '~'); }
TEST(pf_c, "caractère '\\0' (compte 1)") { PF("%c", 0); PF("a%cb", 0); PF("%c%c%c", 0, 'x', 0); }
TEST(pf_c, "plusieurs %c")             { PF("%c%c%c", 'a', 'b', 'c'); PF("%c %c %c ", '1', '2', '3'); }
TEST(pf_c, "texte autour")            { PF("-> %c <-", 'Z'); PF("%cfin", '!'); PF("debut%c", '?'); }
TEST(pf_c, "valeurs > 127 et négatives") { PF("%c", 200); PF("%c", 255); PF("%c", -1); PF("%c", 128); }
TEST(pf_c, "les 256 valeurs")
{
	for (int c = 0; c < 256; c++)
		PF("[%c]", c);
}

/* ================================================================= %s == */
TEST(pf_s, "chaînes simples")         { PF("%s", "hello"); PF("%s", "42"); PF("[%s]", "a b c"); }
TEST(pf_s, "chaîne vide")             { PF("%s", ""); PF("[%s]", ""); PF("%s%s%s", "", "", ""); }
TEST(pf_s, "NULL -> \"(null)\"")      { PF("%s", (char *)NULL); PF("a%sb", (char *)NULL); }
TEST(pf_s, "plusieurs %s")            { PF("%s %s", "Hello", "World"); PF("%s%s", "ab", "cd"); }
TEST(pf_s, "chaîne contenant % et \\n") { PF("%s", "%d %s %%"); PF("%s", "line1\nline2\n"); }
TEST(pf_s, "non-ASCII")               { PF("%s", "caf\xe9 \xff\x80"); }
TEST(pf_s, "longue chaîne (10 000)")
{
	char	*s = gbuf(10001, 'x');

	s[10000] = 0;
	PF("%s", s);
	PF(">%s<%s", s, s);
}
TEST(pf_s, "ne lit pas après le '\\0' (gardé)")
{
	PF("%s", gstr("guarded"));
	PF("%s", gstr(""));
}

/* ================================================================= %p == */
static void	pf_dummy(void)
{
}

TEST(pf_p, "adresses réelles")
{
	int		x;
	char	*h = malloc(4);

	PF("%p", (void *)&x);
	PF("%p", (void *)h);
	PF("%p", (void *)pf_dummy);
	free(h);
}
TEST(pf_p, "NULL -> \"(nil)\"")       { PF("%p", NULL); PF("[%p]", NULL); }
TEST(pf_p, "petites valeurs")         { PF("%p", (void *)1); PF("%p", (void *)15); PF("%p", (void *)16); PF("%p", (void *)255); }
TEST(pf_p, "extrêmes 64 bits")
{
	PF("%p", (void *)UINTPTR_MAX);
	PF("%p", (void *)((uintptr_t)1 << 63));
	PF("%p", (void *)(((uintptr_t)1 << 63) - 1));
	PF("%p", (void *)(uintptr_t)UINT_MAX);
	PF("%p", (void *)((uintptr_t)UINT_MAX + 1));
}
TEST(pf_p, "plusieurs %p")            { PF("%p %p", (void *)1, NULL); PF("%p%p%p", (void *)0x10, (void *)0x20, (void *)0x30); }

/* ============================================================ %d / %i == */
#define INT_SUITE(K, CONV) \
TEST(K, "0, positifs, négatifs") { PF(CONV, 0); PF(CONV, 1); PF(CONV, -1); \
	PF(CONV, 9); PF(CONV, 10); PF(CONV, -10); PF(CONV, 42); PF(CONV, -42); } \
TEST(K, "puissances de 10") { for (long v = 1; v <= 1000000000L; v *= 10) \
	{ PF(CONV, (int)v); PF(CONV, (int)-v); PF(CONV, (int)(v - 1)); } } \
TEST(K, "INT_MAX / INT_MIN") { PF(CONV, INT_MAX); PF(CONV, INT_MIN); \
	PF(CONV, INT_MAX - 1); PF(CONV, INT_MIN + 1); } \
TEST(K, "plusieurs + texte") { PF("a" CONV "b" CONV "c", 1, -2); \
	PF(CONV " " CONV " " CONV, INT_MIN, 0, INT_MAX); } \
TEST(K, "aléatoire (3000 cas)") { for (int k = 0; k < 3000; k++) \
	pf_one_i(__FILE__, __LINE__, CONV, pf_rand_int()); }

INT_SUITE(pf_d, "%d")
INT_SUITE(pf_i, "%i")

/* ================================================================= %u == */
TEST(pf_u, "0 et positifs")           { PF("%u", 0); PF("%u", 1); PF("%u", 42); PF("%u", 4096); }
TEST(pf_u, "UINT_MAX")                { PF("%u", UINT_MAX); PF("%u", UINT_MAX - 1); }
TEST(pf_u, "négatifs vus en unsigned") { PF("%u", -1); PF("%u", -42); PF("%u", INT_MIN); }
TEST(pf_u, "plusieurs + texte")       { PF("%u%u", 1u, 2u); PF("[%u] [%u]", 0u, UINT_MAX); }
TEST(pf_u, "aléatoire (3000 cas)")
{
	for (int k = 0; k < 3000; k++)
		pf_one_u(__FILE__, __LINE__, "%u", pf_rand_uint());
}

/* ============================================================ %x / %X == */
#define HEX_SUITE(K, CONV) \
TEST(K, "0 à 255") { for (unsigned v = 0; v < 256; v++) PF(CONV, v); } \
TEST(K, "valeurs typiques") { PF(CONV, 0xdeadbeef); PF(CONV, 0xcafe); \
	PF(CONV, 0x10); PF(CONV, 0xabcdef); } \
TEST(K, "UINT_MAX, -1, INT_MIN") { PF(CONV, UINT_MAX); PF(CONV, -1); \
	PF(CONV, INT_MIN); PF(CONV, 0x80000000u); } \
TEST(K, "plusieurs + texte") { PF("0x" CONV " " CONV, 255u, 16u); } \
TEST(K, "aléatoire (3000 cas)") { for (int k = 0; k < 3000; k++) \
	pf_one_u(__FILE__, __LINE__, CONV, pf_rand_uint()); }

HEX_SUITE(pf_x, "%x")
HEX_SUITE(pf_X, "%X")

/* ================================================================= %% == */
TEST(pf_pct, "%% seul")               { PF("%%"); PF("%%%%"); PF("%%%%%%"); }
TEST(pf_pct, "%% avec texte")         { PF("100%%"); PF("%%d"); PF("a%%b%%c"); PF("%% %%"); }
TEST(pf_pct, "%% mélangé")            { PF("%d%%", 50); PF("%%%s%%", "x"); PF("%c%%%c", 'a', 'b'); }

/* ============================================================ mélanges == */
TEST(pf_mix, "chaîne vide -> 0")      { PF(""); }
TEST(pf_mix, "texte sans conversion")
{
	PF("Hello, World!");
	PF("\n");
	PF("tab\tnewline\n");
	PF("caf\xe9");
}
TEST(pf_mix, "toutes les conversions")
{
	int	x;

	PF("%c|%s|%p|%d|%i|%u|%x|%X|%%", 'A', "str", (void *)&x, -42, 42, 42u,
		0xabcu, 0xabcu);
	PF("Hello %s, tu as %d ans et %u%% de batterie (%x/%X) %c%c",
		"habretag", 20, 87u, 255u, 255u, ':', ')');
}
TEST(pf_mix, "beaucoup d'arguments (24)")
{
	PF("%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d",
		1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
		21, 22, 23, 24);
	PF("%s%c%d%s%c%d%s%c%d%s%c%d", "a", 'b', 1, "c", 'd', 2, "e", 'f', 3,
		"g", 'h', 4);
}
TEST(pf_mix, "longue sortie (retour > 10 000)")
{
	char	*s = gbuf(5001, 'y');

	s[5000] = 0;
	PF("%s|%s|%d", s, s, 12345);
}
TEST(pf_mix, "aléatoire : texte + conversions mélangées (1000 cas)")
{
	char	fmt[64];

	for (int k = 0; k < 1000; k++)
	{
		const char	*convs = "cspdiuxX";
		char		c = convs[zrand() % 8];

		snprintf(fmt, sizeof(fmt), "%s%%%c%s", zrand() % 2 ? "<" : "",
			c, zrand() % 2 ? ">%%" : "");
		if (c == 'c')
			pf_one_c(__FILE__, __LINE__, fmt, (int)(zrand() % 256));
		else if (c == 's')
			pf_one_s(__FILE__, __LINE__, fmt, pf_rand_str());
		else if (c == 'p')
			pf_one_p(__FILE__, __LINE__, fmt, pf_rand_ptr());
		else if (c == 'd' || c == 'i')
			pf_one_i(__FILE__, __LINE__, fmt, pf_rand_int());
		else
			pf_one_u(__FILE__, __LINE__, fmt, pf_rand_uint());
	}
}

/* ========================================================= cas limites == */
MTEST(pf_edge, "malloc échoue : pas de crash ni de fuite")
{
	int	x;

	ARM();
	ft_printf("%s %d %p %x %c %u %%\n", "abc", -42, (void *)&x, 255u, 'z', 7u);
	DISARM();
}
TEST(pf_edge, "appels successifs indépendants")
{
	PF("%d", 1);
	PF("%s", "deux");
	PF("%x", 3u);
	PF("");
	PF("%c", 'e');
}
VS(pf_edge, "format NULL")
{
	OUT("%d", PICK(ft_printf, r_printf)(NULL));
}
SPEC_TEST(pf_edge, "'%' seul en fin de format")
{
	PF("abc%");
	PF("%");
}
SPEC_TEST(pf_edge, "conversion inconnue (%k, %w)")
{
	PF("%k");
	PF("a%wb");
}

/* ============================================ arguments read as an int == */
/* The %x bug of the moulinette: va_arg(ap, unsigned long) for an int prints
   "ffffffffffffffff" for -1 when the upper half of the slot is not zero.  */
static const int	g_dirty[] = {-1, 0, 1, 42, -42, 255, INT_MAX, INT_MIN,
	(int)0xdeadbeef, 0x7fff, -0x8000, 1000000};

#define DIRTY_TEST(K, CONV) \
TEST(K, "lit un int, pas un long (32 bits hauts sales)") \
{ for (size_t k = 0; k < sizeof(g_dirty) / sizeof(*g_dirty); k++) \
	pf_dirty(__FILE__, __LINE__, CONV, g_dirty[k]); \
	pf_dirty8(__FILE__, __LINE__, CONV " " CONV " " CONV " " CONV " " CONV " " \
		CONV " " CONV " " CONV, g_dirty); }

DIRTY_TEST(pf_d, "%d")
DIRTY_TEST(pf_i, "%i")
DIRTY_TEST(pf_u, "%u")
DIRTY_TEST(pf_x, "%x")
DIRTY_TEST(pf_X, "%X")
TEST(pf_c, "lit un int, pas un long (32 bits hauts sales)")
{
	static const int	v[] = {'a', 'Z', '0', 0, 127, 200, ' ', '\n'};

	for (size_t k = 0; k < sizeof(v) / sizeof(*v); k++)
		pf_dirty(__FILE__, __LINE__, "[%c]", v[k]);
	pf_dirty8(__FILE__, __LINE__, "%c%c%c%c%c%c%c%c", v);
}
TEST(pf_mix, "8 arguments, les derniers sur la pile, bits hauts sales")
{
	pf_dirty8(__FILE__, __LINE__, "%d|%i|%u|%x|%X|%c|%d|%x", g_dirty);
	pf_dirty8(__FILE__, __LINE__, "%x %x %x %x %x %x %x %x", g_dirty + 4);
}

/* random formats of up to 8 conversions, one 64-bit slot per argument (an
   int slot has dirty upper bits: libc reads the low 32 like va_arg(int)) */
TEST(pf_mix, "aléatoire : 8 conversions par format (2000 cas)")
{
	char	fmt[256];
	long	a[8];

	for (int k = 0; k < 2000; k++)
	{
		size_t	l = 0;
		int		n = 1 + (int)(zrand() % 8);

		for (int i = 0; i < n; i++)
		{
			const char	*convs = "cspdiuxX%";
			char		c = convs[zrand() % 9];

			if (zrand() % 2)
				l += (size_t)snprintf(fmt + l, sizeof(fmt) - l, "%s",
					zrand() % 2 ? " " : "<>");
			l += (size_t)snprintf(fmt + l, sizeof(fmt) - l, "%%%c", c);
			if (c == 's')
				a[i] = (long)pf_rand_str();
			else if (c == 'p')
				a[i] = (long)pf_rand_ptr();
			else if (c == 'c')
				a[i] = DIRTY(zrand() % 256);
			else if (c == 'd' || c == 'i')
				a[i] = DIRTY(pf_rand_int());
			else if (c == '%')
				a[i] = 0;
			else
				a[i] = DIRTY(pf_rand_uint());
			if (c == '%')
				i--, n--;
		}
		pf_multi(__FILE__, __LINE__, fmt, a);
	}
}

/* ==================================================== more edge cases == */
TEST(pf_s, "les 255 octets non nuls")
{
	char	s[256];

	for (int i = 1; i < 256; i++)
		s[i - 1] = (char)i;
	s[255] = 0;
	PF("%s", s);
	PF("[%s|%s]", s + 100, s + 254);
}
TEST(pf_s, "plusieurs NULL et chaînes vides")
{
	PF("%s%s%s", (char *)NULL, "", (char *)NULL);
	PF("[%s] [%s] [%s]", "", (char *)NULL, "x");
}
TEST(pf_mix, "format long sans conversion (20 000)")
{
	char	*f = gbuf(20001, 'f');

	f[20000] = 0;
	PF(f);
}
TEST(pf_pct, "%% collé aux conversions")
{
	PF("%%%d%%", 42);
	PF("%%%s", "s");
	PF("%%%c%%%c%%", 'a', 'b');
	PF("%d%%%d", 1, 2);
}
TEST(pf_p, "pointeurs aléatoires (2000 cas)")
{
	for (int k = 0; k < 2000; k++)
		pf_one_p(__FILE__, __LINE__, "%p", pf_rand_ptr());
}
TEST(pf_s, "chaînes aléatoires (2000 cas)")
{
	for (int k = 0; k < 2000; k++)
		pf_one_s(__FILE__, __LINE__, "[%s]", pf_rand_str());
}
TEST(pf_c, "caractères aléatoires (1000 cas)")
{
	for (int k = 0; k < 1000; k++)
		pf_one_c(__FILE__, __LINE__, "%c", (int)(zrand() % 256));
}
