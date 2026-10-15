---
topic: security/zsh-expansion-globbing-arrays
priority: P3
applies_to: "Zsh 5.9.2 expansion: the order of expansions, parameter expansion and word splitting, filename generation (globbing, extended operators, recursive globs, qualifiers), and array and associative array parameters"
retrieved_utc: 2026-10-15
sources: [S-vqwwekes, S-zlyzov2u, S-e6mo6lhk, S-3gkyn5mu, S-cbs5knac]
status: complete
---

# Zsh expansion, globbing and arrays

## Summary
Zsh runs history, alias, process substitution, parameter, command substitution, arithmetic and brace expansion in a fixed order and generates filenames last. Its defaults differ from POSIX sh and Bash in three places that matter in scripts: an unquoted parameter is not split into words, a glob with no match is an error, and arrays are numbered from 1. Globbing is richer than in sh: with `EXTENDED_GLOB` there are negation and repetition operators, `**/` descends directories, and a trailing parenthesised qualifier filters by file type, mode, time or size. Each of the defaults has an option that turns it back into the sh or ksh behaviour (`security/zsh-options-emulation-bash-differences.md`).

## Facts
- The expansions run in this order: history expansion (interactive shells only), alias expansion, then process substitution, parameter expansion, command substitution, arithmetic expansion and brace expansion, left to right on each argument, then filename expansion, with filename generation always last; after them unquoted `\`, `'` and `"` are removed, and with `SH_FILE_EXPANSION` set filename expansion comes right after alias expansion. [DOC S-vqwwekes]
- Words of an unquoted parameter are not split on whitespace unless `SH_WORD_SPLIT` is set, which the manual calls an important difference from other shells; null words are still elided, so with `array=("first word" "" "third word")` `$array` gives two words, while `"${array[@]}"` keeps all three; `${=spec}` splits one expansion by the `SH_WORD_SPLIT` rules even inside double quotes and `${==spec}` turns it off. [DOC S-vqwwekes]
- The parameter expansion flag `s:string:` splits on `string` and `j:string:` joins array words with it, before any field splitting; flags and nesting are allowed, as in `${(@kv)aliases}`, and the pattern forms use the filename generation syntax. [DOC S-vqwwekes]
- With `RC_EXPAND_PARAM` the form `foo${xx}bar` distributes over array elements and an empty array removes the argument; `GLOB_SUBST` makes the results of parameter expansion eligible for filename expansion and generation. [DOC S-e6mo6lhk]
- The FAQ's example: `args $var` with `var="foo bar"` passes one argument by default and two after `setopt shwordsplit`, while an array passes the number of its elements regardless of the option. [DOC S-cbs5knac]
- Filename generation replaces a pattern word by a sorted list of matching names, and `/` must be matched explicitly; with no match the shell gives an error, unless `NULL_GLOB` deletes the word or `NOMATCH` is unset and the word is left unchanged. [DOC S-vqwwekes]
- `*`, `?` and `[...]` (with named classes such as `[:alnum:]`) are the basic operators and `<x-y>` matches a number in a range (`<->` any number); `^x`, `x~y`, `x#` and `x##` need `EXTENDED_GLOB`; grouping `(...)` and `x|y` are available, but a `/` inside a group is an error except in a whole path segment of the form `(pat/)#`. [DOC S-vqwwekes]
- `**/` is a shorthand for `(*/)#` and matches files in the current directory as well as in subdirectories, `***/` is the same but follows symbolic links, and with `GLOB_STAR_SHORT` `**.c` is equivalent to `**/*.c`. [DOC S-vqwwekes]
- A pattern may end in glob qualifiers in parentheses; with `BARE_GLOB_QUAL` a trailing group with no `|` or `(` is taken as qualifiers (doubling the parentheses forces a pattern), and with `EXTENDED_GLOB` the form `(#qx)` is available and can be chained as a logical AND. [DOC S-vqwwekes]
- Qualifiers include `/` (directories), `.` (plain files), `@` (symbolic links), `*` (executable plain files), `x`, `r` and `w` for permissions, `N` (sets `NULL_GLOB` for this pattern), `D` (sets `GLOB_DOTS`) and `n` (sets `NUMERIC_GLOB_SORT`); `*(-/)` lists directories and symbolic links that point to directories. [DOC S-vqwwekes]
- The FAQ's mapping of ksh pattern lists: `!(foo)` is `^foo`, `@(a|b)` is `(a|b)`, `*(foo)` is `(foo)#` and `+(foo)` is `(foo)##`, and `KSH_GLOB` makes the ksh forms work as such. [DOC S-3gkyn5mu]
- An array is assigned with `name=(value ...)`, `set -A name value ...` or `name=([key]=value ...)` and appended to with `name+=(value ...)`; newlines and semicolons inside the parentheses act as white space; with the keyed form `array=(one [3]=three four)` gives four elements, `one`, an empty string, `three` and `four`. [DOC S-zlyzov2u]
- Ordinary arrays can be declared with `typeset -a name`; associative arrays must be declared with `typeset -A name` before assignment, take alternating keys and values, and one assignment may use only one of the two syntaxes `name=(key value ...)` and `name=([key]=value ...)`, which replaces the whole array. [DOC S-zlyzov2u]
- Array elements are numbered from 1 unless `KSH_ARRAYS` is set (from 0, and then only the braced `${foo[2]}` form works); without it a subscript of zero reads as an empty string and writing it is an error, and `KSH_ZERO_SUBSCRIPT` makes 0 and 1 equivalent. [DOC S-zlyzov2u]
- `[*]` and `[@]` select all elements and differ only in double quotes (`"$foo[*]"` is one word, `"$foo[@]"` one word per element); a bare `$name` is the whole array, or with `KSH_ARRAYS` the element `${name[0]}`; `[exp1,exp2]` selects an inclusive range, negative values count from the end, and associative arrays take no ranges. [DOC S-zlyzov2u]
- `path`, `fpath` and similar lowercase parameters are arrays tied to the colon-joined uppercase scalars (`PATH`); unsetting either of the pair unsets both. [DOC S-zlyzov2u]
- The FAQ says individual array elements are strings, so an element of an ordinary array cannot be unset, only set empty or removed by shortening the array. [DOC S-3gkyn5mu]
- Where a script must be portable between zsh and sh, the zsh-only forms (`**/`, qualifiers, `${(flags)name}`, `path` as an array) fail under other shells, so the zsh script carries a `zsh` shebang and `emulate -L zsh`, and a portable script avoids them. [DER S-vqwwekes, S-zlyzov2u: these forms are defined by the zsh manual and the FAQ says shells differ]
- To iterate over files that may be absent without an error in zsh, `*(N)` (or `setopt null_glob` inside a function with `emulate -L zsh`) replaces the sh habit of testing `[ -e "$f" ]` after an unmatched pattern is left literal. [DER S-vqwwekes, S-e6mo6lhk: `NOMATCH` errors on no match, `N` sets `NULL_GLOB` for one pattern]

## Reference
| need | zsh form | source |
|---|---|---|
| split one expansion into words | `${=var}` | S-vqwwekes |
| keep empty array elements | `"${array[@]}"` | S-vqwwekes |
| recursive search | `**/name`, `***/name` (symlinks) | S-vqwwekes |
| all but one pattern | `^foo` or `*~foo` (with `EXTENDED_GLOB`) | S-vqwwekes |
| empty result is not an error | `*(N)` | S-vqwwekes |
| last element of an array | `$array[-1]` | S-zlyzov2u |

Related: `security/zsh-options-emulation-bash-differences.md`, `security/zsh-startup-files-invocation.md`.

## Examples
- SNIPPET: list the plain files under a directory tree without an error when none exist; context: Zsh 5.9.2, `**/` with the `.` and `N` qualifiers; checked: no [DER S-vqwwekes: qualifier list and the `**/` shorthand]
```
print -rl -- /var/log/pl-app/**/*(.N)
```
