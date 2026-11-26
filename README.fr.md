# 🔥 ftorture — testeur 42 : libft, ft_printf, get_next_line, push_swap & modules Python

🇬🇧 [English version](README.md)

> *Ton code va parler.*

**ftorture** fait passer ton projet à la question : chaque test tourne dans son propre
processus, face à la **vraie** fonction de la libc (ou dans un interpréteur Python isolé pour les modules Python). On regarde comment il crashe, ce
qu'il fuit et ce qu'il lit en dehors de sa mémoire.

| Projet | Sujet | Ce qui est testé |
|---|---|---|
| **libft** | v19.3 | les 43 fonctions (parties 1, 2 et 3), ~400 tests + fuzzing |
| **ft_printf** | v12.1 | `cspdiuxX%` + bonus `-0.`, largeur, `# +`, ~22 000 appels comparés à `printf` |
| **get_next_line** | v14.3 | 14 `BUFFER_SIZE`, fichiers, stdin, pipe, erreurs de `read`, bonus multi-fd |
| **push_swap** | v1.2 | erreurs, les 4 stratégies, `--bench`, seuils 100 / 500 nombres, valgrind, bonus `checker` |
| **py00** (`python-module-00`) | v3.0 | *Growing Code* : `ex0`–`ex7`, I/O, récursion, typage, `flake8`, `mypy`, vérifs AST |
| **py01** (`python-module-01`) | v3.2 | *Code Cultivation* : `ex0`–`ex6`, POO, encapsulation, héritage, `flake8`, `mypy`, vérifs AST |

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

1. **Projet** : LIBFT, FT_PRINTF, GNL, PUSH_SWAP, **PYTHON MODULES**, puis tes suites
   personnalisées (`↑ ↓`, `j/k`, ou un chiffre, puis Entrée). PYTHON MODULES ouvre un
   second menu avec chaque module Python (PY00, PY01…) ; `q` ou RETOUR revient au menu
   principal. Le projet du dossier courant est présélectionné (dans le sous-menu pour un
   module Python).
2. **Chemin** : valeur par défaut modifiable, complétion Tab et nouvelle saisie en cas d'erreur.
3. **Options** : Espace/Entrée coche le mode strict, verbose, efficacité, vérifications, norminette
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
torture gnl -f 3,77,4096             # n'importe quels BUFFER_SIZE, même hors liste
torture gnl -f 1,42 --file mon.txt   # seulement ton fichier, avec ces BUFFER_SIZE
torture gnl --file 64k,2M            # fichiers générés de 64 Ko et 2 Mo
torture push_swap ~/push_swap -e     # un push_swap (+ checker), avec l'efficacité
torture ps -f errors,perf500 -v      # quelques suites push_swap, tous les détails
torture py00 ~/python-module-00 -v   # python-module-00 (Growing Code)
torture py01 ~/python-module-01 -c   # python-module-01 (Code Cultivation), mode chill
```

| Option | Effet |
|---|---|
| `-s`, `--speculative` | les erreurs spéculatives (▲) font échouer |
| `-v`, `--verbose` | chaque échec en entier : pourquoi, le code du test, l'appel, un `main.c`, la commande `--repro` |
| `--repro TEST` | recompile un test qui échoue seul avec ton code et le lance sous valgrind (`TEST` est donné par `-v`) |
| `--gdb` | avec `--repro` : lance le test sous gdb |
| `-e`, `--efficiency [N]` | compare chaque fonction à un temps « parfait » calculé pour cette machine, jauge en bas, objectif N % (défaut 50) |
| `-t`, `--target N` | objectif d'efficacité en % (1–100) ; active `-e` |
| `-f`, `--func LISTE` | libft : `ft_split,itoa` · printf : `%d,%s,flag -,précision .` · gnl : n'importe quels BUFFER_SIZE, `1,42,77,100k,def` · push_swap : `errors,simple,bench,perf100,checker…` · python : `ex0,ex7,ft_plot_area` |
| `-p`, `--part N` | libft : 1, 2 ou 3 · printf / gnl / push_swap : 1 (obligatoire) ou 2 (bonus) |
| `--file F\|TAILLE` | gnl : ne teste que ton fichier (comparé ligne à ligne à son contenu), ou un fichier généré de cette taille (`64k`, `2M`, 256M max) ; répétable, séparé par des virgules |
| `-c`, `--chill` | passe les vérifications style/hygiène KO (norminette, flake8/mypy, fichiers en trop, README, includes, hygiène Makefile) en avertissements (▲) |
| `--no-checks` | saute Makefile / norme / nm / prototypes / vérifs AST Python |
| `--no-norm` | saute norminette (C) ou flake8 / mypy (Python) |
| `--no-hidden` | ignore les fichiers/dossiers cachés dans les vérifications des fichiers, includes et norminette |
| `--seed N` | graine du fuzzing (42 par défaut) |
| `--timeout S` | timeout par test (3 s par défaut, 10 s pour gnl, 20 s pour push_swap) |
| `--no-color` | sans couleurs |
| `--lang en\|fr` | choisir la langue de sortie |
| `--list-projects` | lister les projets et versions de sujet |
| `--custom-tests-dir DIR` | remplacer le dossier par défaut des tests personnalisés |

Après installation, utilise `torture` depuis ton projet ou tout autre dossier ;
inutile de le lancer depuis le dépôt ftorture. Les chemins avec espaces sont acceptés.
Le lanceur est uniquement en Python ; aucun wrapper shell n'est fourni.
Conserve le dépôt : le lanceur installé y charge le code Python et les tests C.

À la fin, ftorture lance le `make fclean` de ton projet (libft, ft_printf, push_swap), même après
une erreur ou un Ctrl-C : il ne reste ni `.o`, ni archive, ni binaire. get_next_line est compilée dans le
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

**Sous-dossiers** : libft, ft_printf et push_swap peuvent ranger leurs sources et leurs
headers dans des sous-dossiers (`srcs/`, `includes/`…) ; le header est cherché à la racine
puis dans les sous-dossiers, et chaque dossier qui contient un `.h` sert de `-I` pour les
includes et les prototypes. Le `Makefile`, le `README.md` et l'archive restent à la racine.
get_next_line garde ses 3 fichiers à la racine, comme le demande le sujet.

Dans tous les projets, ce que les `.gitignore` du dossier ignorent (à la racine ou dans
un sous-dossier, avec `!`, `**`, `/` comme git) n'est pas dans ton rendu : les fichiers en
trop, les includes et norminette ne le regardent pas. La ligne « Fichiers en trop » dit
combien d'entrées ont été ignorées ainsi.

| Bloc | Détail |
|---|---|
| **Makefile** | règles `$(NAME) all clean fclean re` (+ `bonus` pour printf), **noms des fichiers bonus** (s'il y a une règle `bonus`, chaque `.c` compilé par `make bonus` mais pas par `make all`, et chaque header que seuls ces fichiers incluent, doit finir en `_bonus.c` / `_bonus.h` ; les fichiers partagés gardent leur nom ; ▲ seulement pour push_swap, dont le sujet liste `*.c` / `*.h` pour le checker), `cc`, `-Wall -Wextra -Werror` sur chaque fichier (lu avec `make -nB`, même avec des `@`), `ar` et pas libtool, pas de `-std=c99`, **relink** (y compris `make bonus`), `clean` / `fclean` |
| **Fichiers** | fichiers à rendre, **fichiers en trop en KO** (fichiers cachés hors `.git` / `.gitignore`, extensions inattendues comme `.py` `.cpp` `.txt` `.o`, dossiers vides ; ce que ton `.gitignore` ignore n'est jamais poussé, donc n'est pas compté), `README.md` (1re ligne en italique, Description / Instructions / Resources, + explication de l'algorithme pour printf) |
| **Code** | norminette (si installée), **`#include` inutiles** (un `<lib.h>` doit fournir quelque chose d'utilisé, un `"x.h"` du projet une de ses fonctions, structs, macros ou libs ; doublons aussi), **fonctions externes interdites** (tout sauf `malloc`, `free`, `write`, avec le fichier fautif ; pour ft_printf, les fonctions de ta `libft/` sont permises et ses propres appels externes vérifiés pareil, et **libft dans l'archive** est KO si `libftprintf.a` appelle une fonction de `libft/libft.a` sans la contenir : la correction lie `libftprintf.a` seule, il faut `cp libft/libft.a $(NAME)` avant `ar rcs`), **variables globales**, fonctions auxiliaires non `static` (libft), fonctions présentes dans l'archive |
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

**Tailles de buffer et fichiers au choix** : `-f` accepte n'importe quelle liste de
`BUFFER_SIZE` (`3,77,4096`, `100k` = 100 000, `10M`, `def`) ; une taille hors de la liste
habituelle a sa propre ligne (8 au maximum) et passe aussi dans le bonus. `--file` remplace
les tests habituels par tes entrées : un fichier texte à toi, lu ligne à ligne et comparé à
son contenu, ou une taille (`64k`, `2M`) qui génère des lignes aléatoires de 0 à 200
caractères, une de 10 000, la dernière sans `\n`. Avec `--file`, le timeout par défaut
grandit avec la taille du fichier et rapetisse avec le `BUFFER_SIZE` (10 s + ~10 µs par
`read()`, 10 min max) ; `--timeout` le remplace.

**La Bible** : chaque passe lit aussi la Bible King James (4,3 Mo, 99 594 lignes, domaine
public, `data/bible-kjv.txt.gz`), un vrai gros fichier texte, avec une taille qui a du
sens pour le buffer : le livre entier de 32 à 10 000 (et sans `-D`), ses premiers
`BUFFER_SIZE × 50 000` octets en dessous de 32, ses 100 premiers Ko au-dessus de 10 000
(une stash de cette taille recopiée après chaque ligne ferait des Go de copies).

**Petits `BUFFER_SIZE` sans attendre 10 minutes** : les lignes très longues (100 000 et
300 000 caractères) sont coupées à 4096 `read()`, donc 4096 caractères avec
`BUFFER_SIZE=1`, toujours largement au-delà du buffer. Une stash refaite par un `strjoin`
après chaque `read()` est quadratique : avant, `BUFFER_SIZE=1` y passait des minutes et
finissait en `T`. La vraie ligne de 100 000 caractères est gardée dans un test ▲ « en moins
de 3 s » qui s'arrête au bout de 3 s et explique pourquoi, et `-e` mesure ce coût.

`BUFFER_SIZE=0` et `BUFFER_SIZE=10000000` comptent comme ▲ : le sujet pose la question
(un buffer de 10 Mo sur la pile crashe), à toi de savoir l'expliquer.

## push_swap

Sujet v1.2 (le nouveau, avec `--simple`, `--medium`, `--complex`, `--adaptive` et
`--bench`). ftorture lance `make`, puis `make bonus` s'il y a une règle bonus, et exécute
**tes binaires** `./push_swap` et `./checker`. Chaque sortie est rejouée sur un simulateur
de piles intégré : stdout ne doit contenir que des opérations (`sa sb ss pa pb ra rb rr
rra rrb rrr`), une par ligne, qui laissent `a` trié et `b` vide.

- **Arguments** : aucun argument (rien ne s'affiche), `INT_MIN` / `INT_MAX`, négatifs ;
  ▲ une seule chaîne `"3 2 1"`, `+3`, `007`.
- **Erreurs** (`Error\n` sur stderr, rien sur stdout) : pas un entier, `1.5`, `12a`, `+`,
  `-`, dépassements (`2147483648`, `-2147483649`, 20 chiffres), doublons, avec ou sans
  sélecteur ; ▲ `""`, `" "`, `+1 1`, `0 -0`, flag inconnu, deux sélecteurs.
- **Déjà trié** : aucune opération, quelle que soit la stratégie.
- **2 à 5 nombres** : toutes les permutations de 3, 4 et 5 nombres ; ▲ 3 nombres en 3 coups
  max, 5 nombres en 12 coups max (ce que la correction attend), `2 1` en un `sa`.
- **Chaque stratégie** (`--simple`, `--medium`, `--complex`, `--adaptive`) : 2 à 500 nombres,
  aléatoires, inversés, `INT_MIN` / `INT_MAX`. `--adaptive` : une entrée par régime du sujet
  (désordre < 0.2, 0.2–0.5, ≥ 0.5), et sans flag = `--adaptive`. ▲ **croissance** : le
  nombre d'opérations est mesuré à 100 puis 400 nombres (`ops ~ n^e`) ; `--medium` doit
  rester sous n^1.75, `--complex` et `--adaptive` sous n^1.4. ▲ les stratégies doivent
  donner des sorties différentes.
- **`--bench`** : stdout inchangé, sur stderr le désordre en % à 2 décimales (vérifié avec
  le calcul du sujet), le nom de la stratégie et sa classe `O(...)`, le total et le compte
  de chacune des 11 opérations ; ▲ `--simple --bench` dans l'autre ordre, `--bench` sur
  une entrée triée.
- **Performances** (stratégie par défaut, listes aléatoires) : 5 listes de 100 nombres
  sous 2000 opérations et 5 de 500 sous 12000 (minimum du sujet) ; ▲ « bien » (< 1500 /
  < 8000) et « excellent » (< 700 / < 5500) sur le pire cas de 10 / 5 listes. Une liste
  aléatoire a un désordre proche de 0.5 : si elle tombe dans le régime medium du sujet
  (0.2 à 0.5), `--adaptive` doit y utiliser son O(n√n), donc dépasser la limite n'y est
  qu'un ▲. Chaque tri est aussi confirmé par le **checker officiel** `checker_linux` s'il
  est trouvé (`--checker CHEMIN`, sinon le dossier du projet, puis `~/Downloads`) : il est
  copié exécutable dans `build/`, ton fichier n'est pas modifié.
- **Bonus `checker`** : les exemples du sujet, `OK` / `KO` (b non vide, liste vide),
  opérations sur piles vides, listes aléatoires des 11 opérations comparées au simulateur,
  tri de 100 et 500 nombres, la sortie de ton push_swap, sans argument ; erreurs
  (arguments invalides, doublons, dépassements, instructions `foo`, `SA`, `" sa"`, `"sa "`,
  `rrrr`) ; ▲ ligne vide, `sa` sans `\n` final.
- **Vérifications** : fichiers (`Makefile`, `*.c`, `*.h`, `README.md`, un dossier
  `libft/`), règles `$(NAME) all clean fclean re` (+ `bonus`), `cc -Wall -Wextra -Werror`,
  relink, `make clean` / `fclean` (`push_swap` et `checker`), README (algorithme, les 2
  logins et la contribution de chacun), norminette, includes, uniquement `read`, `write`,
  `malloc`, `free`, `exit` (`nm` sur les `.o` produits par ton Makefile), pas de variable
  globale (ni `static` globale, ▲), et **valgrind** sur des tris, des erreurs, `--bench` et
  le checker : fuite ou accès invalide = ✘, still reachable = ▲. Sans valgrind, la ligne
  est sautée.

Avec `-e`, l'efficacité de push_swap n'est pas un temps : c'est ta **moyenne
d'opérations** sur 20 listes de 100 et 8 listes de 500 nombres, comparée au seuil
« excellent » du sujet (100 % = 700 ou 5500 opérations). L'objectif à 50 % (défaut)
correspond donc à 1400 et 11 000 opérations.

## Comprendre une erreur (`-v`) et la rejouer (`--repro`)

Avec `-v`, chaque ✘ / ▲ est accompagné de tout ce qu'il faut pour la comprendre et la
reproduire :

```
      ✘ #12 « dst NULL, size = 0 »  t_part1.c:429
        ta fonction crash (SIGSEGV · segmentation fault) alors que l'originale ne crash pas
        attendu   3
        obtenu    CRASH
        pourquoi  La vraie fonction (glibc, BSD, ou la référence pour les
                  fonctions sans original) traite cette entrée sans crasher : …
        test      │ VS(ft_strlcat, "dst NULL, size = 0")
                  │ {
                  │  OUT("%zu", PICK(ft_strlcat, r_strlcat)(NULL, "abc", 0));
                  │ }
        appel     ft_strlcat(NULL, "abc", 0);
        main.c    │ #include "libft.h"
                  │ …
                  │  ft_strlcat(NULL, "abc", 0);  /* attendu : 3 · obtenu : CRASH */
                  cc -g main.c libft.a && valgrind ./a.out
        rejouer   torture libft ~/libft --repro 't_part1.c#97@ft_strlcat'
```

- **pourquoi** : ce que veut dire l'erreur et quoi regarder dans ton code, selon le type
  d'échec (segfault, lecture après la fin d'un buffer gardé, abort, timeout, fuite,
  double free, malloc non protégé, résultat différent de l'original, protection ▲…).
- **test** : le code source du test (ou la ligne de macro qui le génère).
- **appel** et **main.c** : l'appel qui déclenche l'erreur et un main à coller dans ton
  projet (pour get_next_line : un main qui lit `test.txt`).
- **rejouer** : `--repro` recompile **ce test seul** avec ton code, sans fork et avec le
  vrai malloc, puis le lance sous **valgrind** s'il est installé : la ligne fautive de
  ton code s'affiche. Les données du test restent collées à une page interdite (une
  lecture de trop crashe toujours), le même malloc défaillant est reproduit (`mK` dans le
  jeton), et la même graine aléatoire. Ajoute `--gdb` pour le déboguer pas à pas.

```bash
torture libft ~/libft --repro 't_part1.c#97@ft_strlcat'          # valgrind
torture libft ~/libft --repro 't_part1.c#97@ft_strlcat' --gdb    # gdb
```

Sans `-v`, le rapport reste compact ; `ftorture.log` contient toujours tous les détails.

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

## Efficacité (`-e`)

```bash
torture libft ~/libft -e        # objectif 50 % (défaut)
torture gnl ~/get_next_line -t 30
```

Aussi une case dans le menu, juste sous verbose. Il n'y a pas d'implémentation de
référence : chaque charge de travail déclare le **travail minimal** d'une répétition,
ce qu'une implémentation parfaite ne peut pas éviter (`ft_strlen` sur 1000
caractères = 1 appel + 1000 octets lus ; `ft_putstr_fd` = la longueur + **un seul**
`write()` ; get_next_line = un `read()` par `BUFFER_SIZE` octets, chaque octet cherché
et copié une fois, un `malloc` par ligne). ftorture mesure une fois, **sur ta
machine**, le coût de chaque unité avec la boucle la plus serrée qui la fait
(compilée comme le tester, `-O0`, données dans le cache L1, la plus rapide de
plusieurs formes de boucle, meilleur temps sur 20) : tour de boucle, octet lu /
copié / écrit / comparé, appel, comparaison, chiffre, maillon de liste,
`malloc`+`free`, gros `malloc`, appel système, octet ramené par `read()`. Le **temps
parfait** est la somme.

**efficacité = temps parfait / ton vrai temps** : 100 % = aucun travail inutile. Ta
fonction tourne dans son propre processus (malloc non instrumenté), calibrée à
~15 ms de répétitions, meilleur temps par répétition sur 3 passes. Chaque fonction a
son `⚡ N%` sur sa ligne ; la jauge du bas montre la moyenne géométrique (chaque
valeur gardée entre 1 % et 200 %) avec un repère `┃` à l'objectif, les fonctions en
dessous et les principaux coûts de la machine. Un peu plus de 100 % peut arriver (le
code -O0 de ta boucle peut être un poil plus serré que la boucle de calibrage, ou tu
compiles en `-O2`). L'efficacité est indicative : elle ne fait jamais passer le run
en KO.

Ce qui coûte en général : un `write()` par caractère (un appel système coûte des
centaines d'opérations sur des octets : `ft_putstr_fd`, `ft_printf`), lire ou copier
deux fois les mêmes données (`ft_strlcpy` qui calcule la longueur puis copie,
`ft_split`), reparcourir une liste pour chaque maillon (`ft_lstmap`), une stash de
get_next_line refaite par un `strjoin` après chaque `read()` (quadratique en la
longueur d'une ligne) ou un buffer de `BUFFER_SIZE` alloué à chaque appel. Pas de
mesure de GNL sans `-D BUFFER_SIZE`.

Les charges de travail et leur `COST()` sont dans `src/*/b_*.c` ; `ftorture.log` donne
le temps parfait et le vrai temps de chaque fonction et tous les coûts de la machine
(`FTORTURE_BENCH_DEBUG=1` les affiche en direct).

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
src/push_swap/                    tests push_swap (t_push_swap.c, t_checker.c, simulateur ps.c)
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
