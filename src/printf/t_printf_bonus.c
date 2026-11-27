/* ************************************************************************** */
/*  ft_printf — BONUS PART: '-0.' + minimum width, '# +'                      */
/*  Run against the archive built by `make bonus`.                            */
/*  Only combinations DEFINED by the C standard are errors; undefined ones   */
/*  (%05s, %.3c, %#d, %+u, ...) are speculative (▲).                         */
/* ************************************************************************** */
#include "pf.h"

/* ============================================================ flag '-' == */
TEST(pf_minus, "entiers alignés à gauche") { PF("%-5d|", 42); PF("%-5d|", -42); PF("%-5i|", 7); PF("%-1d|", 12345); PF("%-6u|", 7u); }
TEST(pf_minus, "hexa alignés à gauche")    { PF("%-8x|", 255u); PF("%-8X|", 255u); PF("%-3x|", 0u); }
TEST(pf_minus, "%s / %c / %p à gauche")
{
	PF("%-10s|", "abc");
	PF("%-5s|", "");
	PF("%-2s|", "longer");
	PF("%-3c|", 'x');
	PF("%-3c|", 0);
	PF("%-20p|", (void *)0x1234);
	PF("%-12p|", NULL);
}
TEST(pf_minus, "'-' répété")               { PF("%--5d|", 1); PF("%---8s|", "ab"); }

/* ============================================================ flag '0' == */
TEST(pf_zero, "entiers complétés par des 0") { PF("%05d", 42); PF("%05d", -42); PF("%05i", 0); PF("%01d", 5); PF("%03d", 12345); }
TEST(pf_zero, "INT_MIN / UINT_MAX")          { PF("%012d", INT_MIN); PF("%015u", UINT_MAX); }
TEST(pf_zero, "hexa et unsigned")            { PF("%08x", 0xabu); PF("%08X", 0xabu); PF("%010u", 42u); PF("%04x", 0u); }
TEST(pf_zero, "'-' annule '0'")              { PF("%-05d|", 42); PF("%0-5d|", -42); PF("%-08x|", 255u); }

/* ======================================================= précision '.' == */
TEST(pf_prec, "entiers : nombre minimal de chiffres")
{
	PF("%.3d", 7);
	PF("%.3d", -7);
	PF("%.10d", INT_MIN);
	PF("%.1d", 42);
	PF("%.5i", -123);
	PF("%.5u", 42u);
	PF("%.4x", 0xau);
	PF("%.4X", 0xau);
}
TEST(pf_prec, "précision 0 et valeur 0 -> rien")
{
	PF("[%.0d]", 0);
	PF("[%.d]", 0);
	PF("[%.0i]", 0);
	PF("[%.0u]", 0u);
	PF("[%.0x]", 0u);
	PF("[%.0X]", 0u);
	PF("[%.0d]", 1);
}
TEST(pf_prec, "%s tronquée")
{
	PF("%.3s", "abcdef");
	PF("[%.0s]", "abc");
	PF("[%.s]", "abc");
	PF("%.10s", "abc");
	PF("[%.2s]", "");
	PF("%.1s%.2s%.3s", "xyz", "xyz", "xyz");
}
TEST(pf_prec, "'0' ignoré avec une précision")
{
	PF("%08.3d", 7);
	PF("%08.3d", -7);
	PF("%08.5x", 0xabu);
	PF("%06.0d", 0);
}

/* ============================================================ largeur == */
TEST(pf_width, "largeur simple")
{
	PF("%5c|", 'a');
	PF("%5c|", 0);
	PF("%5s|", "ab");
	PF("%10s|", "");
	PF("%1s|", "abc");
	PF("%5d|", 42);
	PF("%3d|", 12345);
	PF("%12u|", UINT_MAX);
	PF("%8x|", 0xbeefu);
	PF("%20p|", (void *)0xdeadbeef);
	PF("%15p|", NULL);
}
TEST(pf_width, "largeur + précision")
{
	PF("%8.3d|", 7);
	PF("%-8.3d|", -7);
	PF("%8.3s|", "abcdef");
	PF("%-8.3s|", "abcdef");
	PF("[%8.0d]", 0);
	PF("%8.5x|", 0xabu);
	PF("%10.4u|", 42u);
}
TEST(pf_width, "grande largeur (100)")      { PF("%100d|", 1); PF("%-100s|", "x"); }

/* ============================================================ flag '#' == */
TEST(pf_hash, "0x / 0X devant")           { PF("%#x", 42u); PF("%#X", 42u); PF("%#x", UINT_MAX); PF("%#X", 0xabcdefu); }
TEST(pf_hash, "valeur 0 : pas de 0x")    { PF("%#x", 0u); PF("%#X", 0u); PF("[%#.0x]", 0u); }
TEST(pf_hash, "# avec largeur / 0 / -")  { PF("%#10x|", 255u); PF("%#-10x|", 255u); PF("%#010x|", 255u); PF("%#.5x|", 255u); PF("%#8.3X|", 10u); }

/* ============================================================ flag ' ' == */
TEST(pf_space, "espace devant les positifs") { PF("% d", 42); PF("% d", -42); PF("% d", 0); PF("% i", 7); PF("% d", INT_MAX); PF("% d", INT_MIN); }
TEST(pf_space, "espace + largeur / précision") { PF("% 5d|", 42); PF("% .3d", 7); PF("% 05d", 42); PF("%- 5d|", 42); PF("% -5d|", -42); }

/* ============================================================ flag '+' == */
TEST(pf_plus, "signe toujours affiché")   { PF("%+d", 0); PF("%+d", 42); PF("%+d", -42); PF("%+i", 7); PF("%+d", INT_MAX); PF("%+d", INT_MIN); }
TEST(pf_plus, "'+' l'emporte sur ' '")    { PF("%+ d", 42); PF("% +d", 42); PF("%+ d", -42); }
TEST(pf_plus, "+ avec largeur / 0 / . / -") { PF("%+5d|", 42); PF("%+.3d", 7); PF("%+05d", 42); PF("%-+5d|", 42); PF("%+08.3d|", -7); }

/* ======================================================= combinaisons == */
/* random but DEFINED combinations: flags allowed for each conversion       */
static void	gen_fmt(char *fmt, size_t sz, char *conv)
{
	static const char	*convs = "cspdiuxX";
	const char			*flags;
	char				c = convs[zrand() % 8];
	size_t				j = 0;
	int					n;

	if (c == 'd' || c == 'i')
		flags = "-0 +";
	else if (c == 'u')
		flags = "-0";
	else if (c == 'x' || c == 'X')
		flags = "-0#";
	else
		flags = "-";
	fmt[j++] = '[';
	fmt[j++] = '%';
	n = (int)(zrand() % 4);
	while (n-- > 0)
		fmt[j++] = flags[zrand() % strlen(flags)];
	if (zrand() % 3)
		j += (size_t)snprintf(fmt + j, sz - j, "%u", zrand() % 25 + 1);
	if (strchr("diuxXs", c) && zrand() % 2)
	{
		fmt[j++] = '.';
		if (zrand() % 4)
			j += (size_t)snprintf(fmt + j, sz - j, "%u", zrand() % 16);
	}
	fmt[j++] = c;
	fmt[j++] = ']';
	fmt[j] = 0;
	*conv = c;
}

TEST(pf_combo, "aléatoire : combinaisons définies (5000 cas)")
{
	char	fmt[48];
	char	c;

	for (int k = 0; k < 5000; k++)
	{
		gen_fmt(fmt, sizeof(fmt), &c);
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
TEST(pf_combo, "plusieurs conversions flaggées")
{
	PF("%-5d|%05d|%.3d|%+d|% d|%#x", 1, 2, 3, 4, 5, 6u);
	PF("[%10.3s][%-10p][%#08X][%+.0d]", "abcdef", (void *)0x42, 0xffu, 0);
}
MTEST(pf_combo, "malloc échoue : pas de crash ni de fuite")
{
	ARM();
	ft_printf("%-10s|%05d|%#x|%+.3d|%20p\n", "abc", -42, 255u, 7, NULL);
	DISARM();
}

/* ================================== cas indéfinis (▲ si différent de glibc) */
SPEC_TEST(pf_undef, "'0' avec %s / %c / %p")  { PF("%05s", "ab"); PF("%05c", 'a'); PF("%020p", (void *)0x42); }
SPEC_TEST(pf_undef, "précision sur %c / %p")  { PF("%.3c", 'a'); PF("%.20p", (void *)0x42); }
SPEC_TEST(pf_undef, "'#' hors x/X")            { PF("%#d", 42); PF("%#s", "a"); PF("%#c", 'a'); }
SPEC_TEST(pf_undef, "'+' / ' ' hors d/i")      { PF("%+u", 42u); PF("% x", 42u); PF("%+s", "a"); PF("% p", (void *)1); }
SPEC_TEST(pf_undef, "%s NULL avec largeur / précision")
{
	PF("[%10s]", (char *)NULL);
	PF("[%-10s]", (char *)NULL);
	PF("[%.3s]", (char *)NULL);
	PF("[%.6s]", (char *)NULL);
}
SPEC_TEST(pf_undef, "flags sur %%")            { PF("%5%"); PF("%-5%|"); PF("%05%"); }

/* ============================================ arguments read as an int == */
/* same check as the mandatory part, through the flags                   */
TEST(pf_combo, "flags : lit un int, pas un long (32 bits hauts sales)")
{
	static const char	*fmts[] = {"%-12d|", "%012d", "%.10d", "%+d", "% d",
		"%#x", "%#X", "%08x", "%-10u|", "%.12u", "%10.5d", "%-+8i|", "%#.8x",
		"%5c|", "%-5c|"};
	static const int	v[] = {-1, 0, 42, -42, INT_MAX, INT_MIN, 255,
		(int)0xdeadbeef};

	for (size_t f = 0; f < sizeof(fmts) / sizeof(*fmts); f++)
		for (size_t k = 0; k < sizeof(v) / sizeof(*v); k++)
		{
			if (fmts[f][strlen(fmts[f]) - 1] == 'c'
				|| fmts[f][strlen(fmts[f]) - 2] == 'c')
				pf_dirty(__FILE__, __LINE__, fmts[f], 'A' + (int)k);
			else
				pf_dirty(__FILE__, __LINE__, fmts[f], v[k]);
		}
}

/* random flags, width and precision on every conversion they are defined
   for, compared with printf                                             */
TEST(pf_combo, "aléatoire : flags + largeur + précision (3000 cas)")
{
	char	fmt[64];

	for (int k = 0; k < 3000; k++)
	{
		const char	*convs = "diuxXscp";
		char		c = convs[zrand() % 8];
		size_t		l = 0;

		fmt[l++] = '%';
		if (zrand() % 3 == 0)
			fmt[l++] = '-';
		else if (zrand() % 2 && c != 's' && c != 'c' && c != 'p')
			fmt[l++] = '0';
		if ((c == 'd' || c == 'i') && zrand() % 3 == 0)
			fmt[l++] = zrand() % 2 ? '+' : ' ';
		if ((c == 'x' || c == 'X') && zrand() % 3 == 0)
			fmt[l++] = '#';
		if (zrand() % 2)
			l += (size_t)snprintf(fmt + l, sizeof(fmt) - l, "%u", zrand() % 25);
		if (c != 'c' && c != 'p' && zrand() % 2)
			l += (size_t)snprintf(fmt + l, sizeof(fmt) - l, ".%u", zrand() % 15);
		fmt[l++] = c;
		fmt[l++] = '|';
		fmt[l] = 0;
		/* '0' with a precision is ignored by printf for integers: defined */
		if (c == 's')
			pf_one_s(__FILE__, __LINE__, fmt, pf_rand_str());
		else if (c == 'c')
			pf_one_c(__FILE__, __LINE__, fmt, (int)(zrand() % 256));
		else if (c == 'p')
			pf_one_p(__FILE__, __LINE__, fmt, pf_rand_ptr());
		else if (c == 'd' || c == 'i')
			pf_one_i(__FILE__, __LINE__, fmt, pf_rand_int());
		else
			pf_one_u(__FILE__, __LINE__, fmt, pf_rand_uint());
	}
}
