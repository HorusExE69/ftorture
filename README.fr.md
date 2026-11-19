# 🔥 ftorture — testeur 42 : libft, ft_printf & get_next_line

🇬🇧 [English version](README.md)

> *Ton code va parler.*

**ftorture** fait passer ton projet à la question : chaque test tourne dans son propre
processus, face à la **vraie** fonction de la libc. On regarde comment il crashe, ce
qu'il fuit et ce qu'il lit en dehors de sa mémoire.

| Projet | Sujet | Ce qui est testé |
|---|---|---|
| **libft** | v19.3 | les 43 fonctions (parties 1, 2 et 3), ~400 tests + fuzzing |
| **ft_printf** | v12.1 | `cspdiuxX%` + bonus `-0.`, largeur, `# +`, ~22 000 appels comparés à `printf` |
| **get_next_line** | v14.3 | 14 `BUFFER_SIZE`, fichiers, stdin, pipe, erreurs de `read`, bonus multi-fd |

Inspiré de [Caesarovich/zft](https://github.com/Caesarovich/zft) : moteur C et
orchestration Python modulaire. Dépendances : **Linux**, **Python 3.10+**, `cc`,
`make` et `nm`. Installation, orchestration et vérifications sont en Python.
Aucun paquet pip requis ; norminette reste facultative.

## Installation

```bash
git clone https://github.com/HorusExE69/ftorture.git ~/ftorture
cd ~/ftorture && python3 install.py
```

`install.py` crée directement le lanceur Python exécutable `~/.local/bin/torture`.
Aucun alias. Tu dois ajouter `~/.local/bin` au PATH. L'installateur détecte le shell
actuel (ou utilise `$SHELL`) et vérifie sa configuration : `.zshrc` pour zsh
(`$ZDOTDIR` respecté), `.bashrc` pour bash, `config.fish` pour fish
(`$XDG_CONFIG_HOME` respecté), `.profile` pour sh/dash/ksh. Si l'entrée manque, il
affiche la ligne puis **demande ton autorisation** avant de l'ajouter. Un refus ou
une installation non interactive ne modifie rien : ajoute alors la ligne toi-même.
Les entrées existantes ne sont pas dupliquées. La réinstallation supprime
les anciens lanceurs de `~/.local/applications` uniquement s'ils appartiennent à ftorture.
Vérifie que `~/.local/bin` est dans ton `PATH` (redémarre le shell si besoin).
Le lanceur conserve le dossier courant et transmet tous les arguments.
Pour mettre à jour un dépôt `main` propre depuis le **dépôt original**
(`https://github.com/HorusExE69/ftorture.git`), lance `python3 install.py --update`.
Les modifications locales et les historiques divergents ne sont pas écrasés.
Supprime tout ancien alias `torture` restant dans ta configuration shell.

Pour désinstaller la commande : `python3 install.py --delete --confirm`.
Les deux options sont obligatoires. Seuls
le lanceur géré `~/.local/bin/torture` et sa cible historique gérée sont supprimés.
Les fichiers étrangers sont refusés ; le PATH, les autres commandes, le dépôt et
les tests personnalisés sont conservés. La commande peut être répétée sans risque.

## Utilisation

La langue suit la locale (`fr_*` : français, sinon anglais). Utilise
`--lang fr` ou `--lang en` pour choisir la langue du menu, des tests et du rapport.

### Menu interactif

```bash
torture
```

Le TUI rétro original est conservé en Python : logo pixel, couleurs vertes et trois écrans.

1. **Projet** : LIBFT, FT_PRINTF, GNL (`↑ ↓`, `j/k`, ou `1/2/3`, puis Entrée).
   Le projet du dossier courant est présélectionné.
2. **Chemin** : valeur par défaut modifiable, complétion Tab et nouvelle saisie en cas d'erreur.
3. **Options** : Espace/Entrée coche le mode strict, verbose, vérifications, norminette
   et ignorer les fichiers cachés ; sélectionner **LANCER LA TORTURE**. `q` quitte les menus.

Les options CLI sans projet initialisent le menu. `--lang fr` garde les libellés
français, `--no-color` garde la disposition sans couleurs. Le terminal et le curseur
sont restaurés à la sortie, même après une interruption.

### En ligne de commande

```bash
torture libft ~/libft                # une libft
torture printf ~/ft_printf           # un ft_printf (obligatoire + bonus)
torture gnl ~/get_next_line          # une get_next_line (tous les BUFFER_SIZE)
torture ~/ft_printf -s               # projet détecté tout seul
torture libft -f split,itoa -v       # quelques fonctions, avec tous les détails
torture printf -f %d,"flag -"        # quelques conversions / flags
torture printf -p 1                  # seulement la partie obligatoire
torture gnl -f 1,42,9999             # seulement ces BUFFER_SIZE
```

| Option | Effet |
|---|---|
| `-s`, `--speculative` | les erreurs spéculatives (▲) font échouer |
| `-v`, `--verbose` | affiche le détail de chaque échec |
| `-f`, `--func LISTE` | libft : `ft_split,itoa` · printf : `%d,%s,flag -,précision .` · gnl : `1,42,def` (BUFFER_SIZE) |
| `-p`, `--part N` | libft : 1, 2 ou 3 · printf / gnl : 1 (obligatoire) ou 2 (bonus) |
| `--no-checks` | saute Makefile / norme / nm / prototypes |
| `--no-norm` | saute norminette |
| `--no-hidden` | ignore les fichiers/dossiers cachés dans les vérifications des fichiers et includes |
| `--seed N` | graine du fuzzing (42 par défaut) |
| `--timeout S` | timeout par test (3 s par défaut, 10 s pour gnl) |
| `--no-color` | sans couleurs |
| `--lang en\|fr` | choisir la langue de sortie |
| `--list-projects` | lister les projets et versions de sujet |
| `--custom-tests-dir DIR` | remplacer le dossier par défaut des tests personnalisés |

Après installation, utilise `torture` depuis ton projet ou tout autre dossier ;
inutile de le lancer depuis le dépôt ftorture. Les chemins avec espaces sont acceptés.
Le lanceur est uniquement en Python ; aucun wrapper shell n'est fourni.
Conserve le dépôt : le lanceur installé y charge le code Python et les tests C.

À la fin, ftorture lance le `make clean` de ton projet (libft, ft_printf), même après
une erreur ou un Ctrl-C : il ne reste aucun `.o`. get_next_line est compilée dans le
dossier de ftorture, donc ton dépôt reste propre. Le rapport complet sans couleurs est écrit dans
`ftorture.log`, dans le dossier de ftorture, jamais dans ton projet.

### Tests personnalisés

Ajoute tes tests sans modifier ftorture : place des manifestes JSON versionnés et
leurs scripts dans `${XDG_CONFIG_HOME:-$HOME/.config}/ftorture/tests/`. Ils apparaissent
après les projets intégrés dans le menu principal avec un libellé cyan **[CUSTOM]**.
Chaque suite gère compilation/préparation, nettoyage, tests nommés, filtres,
parties, délais, codes de sortie attendus, avertissements spéculatifs et rapports.
N'exécute que des suites fiables : elles disposent de tes permissions, sans sandbox.

```bash
torture --custom-tests-dir ~/ftorture/examples/custom-tests custom-readme /chemin/projet -v
```

Le [guide des tests personnalisés](docs/custom-tests.md) décrit le format, un
exemple et les limites. Les tests C natifs restent extensibles via `Project`.

### Architecture Python et ajout de projets

Python gère les arguments, la détection, les compilations, les passes obligatoires
et bonus, les appels du moteur C, les codes de retour et le nettoyage. Le moteur C
conserve son comportement et les rapports bilingues. Les vérifications natives de `ftorture/subject/`
produisent `build/<projet>/checks.txt`. Les diagnostics du compilateur et des outils
sont dans `build/<projet>/checks/`. Un verrou protège les artefacts et rapports
contre les exécutions concurrentes.
L'analyse des includes est heuristique : aucun verdict sur un en-tête non résolu.
Vérifie manuellement les cas impliquant des macros complexes ou la compilation conditionnelle.

`ftorture/registry.py` réunit les projets intégrés et les manifestes personnalisés
pour la CLI et le TUI. Ajoute un module dans `ftorture/projects/`, implémente `Project` (`validate`,
`checks`, `run`, `cleanup`), puis enregistre `PROJECT` dans
`ftorture/projects/__init__.py`. La CLI et le menu utilisent ce registre.
Les métadonnées `requires_compiler` et `requires_makefile` permettent d'intégrer
des stratégies sans compilateur C ni Makefile.
`ArchiveProject` fournit la stratégie Makefile/archive ; `GnlProject` illustre la
compilation directe des sources. Les nouveaux projets doivent écrire leurs
vérifications en Python en réutilisant `ftorture/subject/` et `CheckReport`. Voir le
[skill de création de testeurs](skills/ftorture-new-testers/SKILL.md).

`ftorture/runtime.py` centralise les sous-processus, options et chemins ;
`ftorture/ui.py` et `language.py` gèrent le menu et la langue. Validation :
`python3 -m unittest discover -s tests -v`. Les tests utilisent des projets
temporaires mais écrasent `build/` et `ftorture.log`. Codes de retour : `0` succès,
`1` tests/vérifications en échec, `2` erreur du lanceur ou de compilation,
`130` interruption. Un bonus ignoré n'est jamais présenté comme validé.
Voir aussi le [guide de validation](docs/validation.md) pour comparer les versions
Bash et Python sur des copies temporaires d'un vrai projet libft.

## Vérifications (libft et ft_printf)

| Bloc | Détail |
|---|---|
| **Makefile** | règles `$(NAME) all clean fclean re` (+ `bonus` pour printf), `cc`, `-Wall -Wextra -Werror` sur chaque fichier (lu avec `make -nB`, même avec des `@`), `ar` et pas libtool, pas de `-std=c99`, **relink** (y compris `make bonus`), `clean` / `fclean` |
| **Fichiers** | fichiers à rendre, **fichiers en trop en KO** (fichiers cachés hors `.git` / `.gitignore`, extensions inattendues comme `.py` `.cpp` `.txt` `.o`, dossiers vides), `README.md` (1re ligne en italique, Description / Instructions / Resources, + explication de l'algorithme pour printf) |
| **Code** | norminette (si installée), **`#include` inutiles** (un `<lib.h>` doit fournir quelque chose d'utilisé, un `"x.h"` du projet une de ses fonctions, structs, macros ou libs ; doublons aussi), **fonctions externes interdites** (tout sauf `malloc`, `free`, `write`, avec le fichier fautif), **variables globales**, fonctions auxiliaires non `static` (libft), fonctions présentes dans l'archive |
| **Prototypes** | chaque prototype du header comparé par le compilateur au **man Linux** / sujet, `t_list` exacte (libft), header qui compile seul |

## libft

- **Mémoire gardée** : les chaînes de test sont collées à une page interdite, donc la
  moindre lecture au-delà de la fin crashe (`strlcat`, `strnstr`, `substr`, `memchr`…).
- **malloc instrumenté** (`-Wl,--wrap=malloc,--wrap=free`) :
  - un octet écrit hors d'un bloc : crash ; utilisation après `free` : crash
  - **double free** : signalé ; **fuites** : tout bloc non libéré à la fin du test
  - taille allouée vérifiée (`strdup`, `itoa`, `split`…)
  - blocs neufs remplis de `0xA5` : un `calloc` qui ne met pas à zéro se voit
  - **protection des malloc** (`M`) : le test est rejoué en faisant échouer le 1er, le
    2e, le 3e… malloc ; il faut renvoyer `NULL` sans crash ni fuite (`ft_split`, `ft_lstmap`)
- **Fuzzing** contre la glibc (ou BSD pour `strlcpy`, `strlcat`, `strnstr`).

## ft_printf

Chaque appel lance **ton `ft_printf`**, puis **le vrai `printf`** avec les mêmes
arguments, chacun avec sa sortie redirigée vers un fichier. On compare la **sortie
octet par octet** (y compris les `\0` de `%c`) et la **valeur de retour**.

- **Partie obligatoire** (archive de `make`) : chaque conversion `c s p d i u x X %`
  (valeurs limites, `NULL` → `(null)` / `(nil)`, les 256 caractères, `INT_MIN`,
  `UINT_MAX`, pointeurs 64 bits…), mélanges, 24 arguments, sorties de plus de
  10 000 octets, et du fuzzing.
- **Bonus** (archive de `make bonus`, testée dans une deuxième passe) : chaque flag
  (`-`, `0`, `.`, largeur, `#`, espace, `+`), leurs interactions (`'-'` annule `'0'`,
  `'+'` l'emporte sur `' '`, `.0` avec la valeur 0…) et **5 000 combinaisons aléatoires**
  valides selon la norme C.
- **Cas indéfinis** (`%05s`, `%.3c`, `%#d`, `%+u`, `%s` NULL avec précision, flags sur
  `%%`…) : ▲ seulement, s'ils diffèrent de la glibc.
- **Mémoire** : fuites détectées, et malloc rendu défaillant (pas de crash ni de fuite).
- **Format `NULL`** : comparé au crash de la vraie fonction (règle ci-dessous).

Si ton Makefile n'a pas de règle `bonus`, seule la partie obligatoire est testée et le
résumé le dit.

## get_next_line

Pas de Makefile dans ce projet : ftorture compile tes fichiers lui-même, dans son dossier
`build/` (rien n'est écrit dans ton dépôt), **une fois par `BUFFER_SIZE`**. Chaque taille
donne une ligne du rapport : 1, 2, 3, 5, 7, 10, 42, 100, 1024, 9999, 100 000,
10 000 000, la valeur par défaut (sans `-D`), et 0.

- **Contenus** : fichier vide, une ligne avec ou sans `\n`, que des `\n`, lignes de
  `BUFFER_SIZE - 1`, `BUFFER_SIZE` et `BUFFER_SIZE + 1` caractères, lignes de 10 000 et
  100 000 caractères, 5 000 lignes d'un caractère, gros fichier de ~80 Ko, caractères
  non-ASCII.
- **Chaque ligne renvoyée** est comparée à celle attendue, doit être un bloc `malloc`
  assez grand (pas un pointeur vers un buffer `static`) ; après la dernière ligne,
  `get_next_line` doit renvoyer `NULL`, puis encore `NULL`.
- **Autres fd** : entrée standard, **pipe** alimenté par petits morceaux (des `read`
  partiels), fd `-1`, jamais ouvert ou fermé, dossier.
- **Erreurs** : un `read()` qui renvoie `-1` au milieu du fichier (il faut renvoyer
  `NULL`, puis repartir proprement sur un nouveau fichier), malloc défaillant, fuites.
- **« Lit le minimum »** : `read` est instrumenté, et lire tout le fichier pour renvoyer
  la première ligne est une erreur.
- **Bonus** (fichiers `_bonus`) : fichiers lus en alternance, un fichier fini avant les
  autres, fd 1000, stdin, 50 fichiers ouverts en même temps, fd invalides entre deux
  lectures, et **une seule variable `static`** (vérifié avec `nm`). Les tests obligatoires
  tournent aussi sur la version bonus.
- **Vérifications** : les 3 fichiers à rendre (+ les 3 `_bonus`), compilation avec
  `-Wall -Wextra -Werror -D BUFFER_SIZE=42` **et sans `-D`**, uniquement `read`, `malloc`,
  `free` (`lseek` et la libft sont interdits), pas de variable globale, norminette,
  prototype, README avec l'algorithme.

`BUFFER_SIZE=0` et `BUFFER_SIZE=10000000` comptent comme ▲ : le sujet pose la question
(un buffer de 10 Mo sur la pile crashe), à toi de savoir l'expliquer.

## Ta fonction face à la vraie

Pour les entrées tordues (NULL, `n = 0`, dépassements…), ftorture lance **ta**
fonction et **la vraie** dans deux processus séparés, puis compare :

| ta fonction | la vraie | verdict |
|---|---|---|
| crash | crash | ✔ OK : même comportement que l'originale |
| crash | pas de crash | ✘ **erreur**, même sans `-s` (ex : `ft_memcpy(NULL, NULL, 0)`) |
| pas de crash | crash | ▲ **spéculatif** : tu protèges alors que la libc ne le fait pas |
| pas de crash | pas de crash | les résultats doivent être identiques |

Pour les parties 2 et 3 de la libft (pas d'originale dans la libc), la référence est une
implémentation simple, sans protection contre NULL.

Les ▲ sont des avertissements : ils ne font pas échouer ftorture, sauf avec `-s`. À toi
de savoir les défendre en correction.

## Légende

| | |
|---|---|
| `✔` | ok |
| `✔` (cyan) | crash identique à la libc (accepté) |
| `✘` | erreur |
| `S` | crash (segfault, bus error, abort) |
| `T` | timeout, sûrement une boucle infinie |
| `L` | fuite mémoire |
| `M` | test de protection des malloc |
| `▲` | spéculatif |

## Ajouter un test

```
src/engine.c, memtrack.c, zft.h   moteur commun (fork, mémoire gardée, rapport)
src/libft/                        tests libft (t_part1-3.c) + références
src/printf/                       tests ft_printf (t_printf.c, t_printf_bonus.c)
src/gnl/                          tests get_next_line (t_gnl.c, t_gnl_bonus.c)
protos/                           prototypes attendus
```

**libft :**

```c
TEST(ft_strlen, "mon test")
{
	EQ_SZ(ft_strlen("abc"), 3);
}

VS(ft_strlen, "comparé à la libc")
{
	OUT("%zu", PICK(ft_strlen, r_strlen)("abc"));
}
```

**ft_printf** (`pf_d`, `pf_s`, `pf_minus`… : la suite où le test apparaît) :

```c
TEST(pf_d, "mon test")
{
	PF("%d|%d", 42, -42);       /* même sortie + même retour que printf */
}

SPEC_TEST(pf_undef, "cas indéfini")
{
	PF("%05s", "ab");           /* ▲ seulement si différent de la glibc */
}
```

**get_next_line** (`GNL_SUITE` = la ligne du BUFFER_SIZE en cours) :

```c
TEST(GNL_SUITE, "mon test")
{
	static const char	d[] = "a\nb\n";
	int					fd = gnl_file(d, sizeof(d) - 1);

	EXPECT_FD(fd, d, sizeof(d) - 1, "mon fichier");   /* toutes les lignes + NULL */
	close(fd);
}
```

- **Assertions** : `CHECK`, `EQ_INT`, `EQ_SZ`, `EQ_PTR`, `EQ_STR`, `EQ_MEM`, `PF`
- **Variantes** : `SPEC_TEST` (▲), `VS` / `VS_SPEC` (comparé à la vraie fonction),
  `MTEST` (malloc défaillant, entre `ARM()` et `DISARM()`)
- **Helpers** : `gstr`, `gmem`, `gbuf` (mémoire gardée), `alloc_size`,
  `cap_open` / `cap_read`, `INPUT` (décrit l'entrée en cas d'échec)

## Licence

GPL-3.0, comme le projet d'origine.
