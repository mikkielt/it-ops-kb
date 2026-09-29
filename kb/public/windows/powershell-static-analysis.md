---
topic: windows/powershell-static-analysis
priority: P3
applies_to: "PowerShell 7.5 and Windows PowerShell 5.1 (#Requires, module manifests, Import-PowerShellDataFile, Get-Command); System.Management.Automation.Language parser API (SDK 7.4 to 7.6); PSScriptAnalyzer 1.18+"
retrieved_utc: 2026-09-29
sources: [S-oodal3ol, S-iass75od, S-3olari7o, S-62qzauot, S-k7hdd27i, S-6jyt4xkf, S-tsdqt57s, S-gw24iv7o, S-f3ndzkct, S-jhjw7ppr, S-oeqxq56y, S-o6gamymj, S-ffmai4hf, S-g6na73gp, S-yx6xgjzj, S-f4p734lc, S-z65pkysn, S-ia7is5xj, S-4bjgu6jw, S-ouafwanl, S-vbfv4per]
status: complete
---

# Reading PowerShell code without running it: #Requires, manifests, the AST and PSScriptAnalyzer

## Summary
A PowerShell repository states its version pins in two places: `#Requires` lines in scripts and the keys of a
module manifest (`.psd1`). Both can be read without executing anything: the language parser returns an AST with
the parsed `#Requires` values, and `Import-PowerShellDataFile` reads a `.psd1` as data. `PSScriptAnalyzer` lints a
tree against a settings file and can check commands and syntax against target PowerShell versions. Several
familiar commands (`Import-Module`, `Test-ModuleManifest`, `Get-Command` with an exact name, running a script with
`#Requires -Modules`) import modules and so can run code: an agent mapping an untrusted repository avoids them.

## Facts
- `#Requires` statements apply globally wherever they sit in the script and must all be met before the script can run; `-Version` gives a minimum `<N>[.<n>]`, `-PSEdition` takes `Core` or `Desktop`, `-RunAsAdministrator` (PowerShell 4.0+) is ignored on non-Windows systems, and `-Modules` takes a name or a hashtable with `ModuleName` plus `ModuleVersion`, `MaximumVersion` or `RequiredVersion`. [DOC S-6jyt4xkf]
- `#Requires -Assembly` is deprecated and does nothing. [DOC S-6jyt4xkf]
- When a script with `#Requires -Modules` runs, PowerShell imports any required module that is not in the session and throws a terminating error if it cannot; running the script is therefore not a side-effect-free way to check its pins. [DOC S-6jyt4xkf]
- `[System.Management.Automation.Language.Parser]::ParseFile(fileName, [ref]tokens, [ref]errors)` parses a script file and returns a `ScriptBlockAst` plus its tokens and parse errors; `ParseInput` does the same for a string. [DOC S-oeqxq56y]
- `ScriptBlockAst.ScriptRequirements` holds everything parsed from the script's `#requires` lines (null when there are none), so the pins are read from the AST without running the script. [DOC S-ffmai4hf]
- `Ast.FindAll(predicate, searchNestedScriptBlocks)` walks the whole tree and returns every node the predicate accepts, e.g. every function definition or command invocation. [DOC S-o6gamymj]
- In a module manifest only `ModuleVersion` is required; every other key is optional. [DOC S-tsdqt57s]
- Manifest `PowerShellVersion` is the minimum engine version; when it is unset, import is not restricted by version. [DOC S-tsdqt57s]
- Manifest `CompatiblePSEditions` accepts `Desktop` and `Core`; Windows PowerShell versions older than 5.1 cannot load a module that uses the key, because `$PSEdition` arrived in 5.1. [DOC S-tsdqt57s]
- Manifest `RequiredModules` entries are a module name, a module specification hashtable (`ModuleName` with `ModuleVersion`, `RequiredVersion` or `MaximumVersion`) or a path; `Import-Module` imports them, or fails when they are missing. [DOC S-tsdqt57s]
- Manifest `RootModule` sets the module type from its extension: `.psm1`/`.ps1` script, `.dll` binary, `.cdxml` CIM, `.psd1` or none a manifest module. [DOC S-tsdqt57s]
- Microsoft's guidance for `FunctionsToExport` and `CmdletsToExport` is an explicit list without wildcards; an unset key or `'*'` exports everything, `@()` exports nothing. [DOC S-tsdqt57s]
- A manifest is evaluated in `Restricted` language mode when a module is imported. [DOC S-tsdqt57s]
- `Import-PowerShellDataFile` reads a `.psd1` as data without invoking its code; by default it is limited to 500 keys and 5000 AST nodes, and `-SkipLimitCheck` lifts the limit. [DOC S-f3ndzkct]
- `Test-ModuleManifest` checks that the files a manifest lists exist and returns a `PSModuleInfo` object even when the manifest has errors. [DOC S-gw24iv7o]
- `Get-Command -Module <name>` lists commands from the named modules; a module imported automatically this way has the same effect as `Import-Module` and can run scripts in the session. [DOC S-jhjw7ppr]
- `Invoke-ScriptAnalyzer -Path <dir> -Recurse` analyses `.ps1`, `.psm1` and `.psd1` files and by default returns one `DiagnosticRecord` per rule violation; `-Settings` takes a `.psd1` path, a hashtable or a preset name. [DOC S-g6na73gp]
- A `PSScriptAnalyzerSettings.psd1` in the project root is picked up automatically when that root is passed as `-Path`. [DOC S-yx6xgjzj]
- Since PSScriptAnalyzer 1.18.0, parse errors come back as diagnostic records with severity `ParseError`; `-EnableExit` sets the exit code to the number of error records. [DOC S-yx6xgjzj, S-g6na73gp]
- Rule `PSUseCompatibleCommands` (disabled by default) checks commands against `TargetProfiles`, platform profiles named `<os>_<arch>_<osver>_<psver>_<psarch>_<dotnetver>_<edition>`; a command absent from the union profile is treated as local and ignored. The bundled profiles end at PowerShell 7.0. [DOC S-f4p734lc]
- Rule `PSUseCompatibleSyntax` (disabled by default) flags syntax unsupported by the listed `TargetVersions` (e.g. `'5.1'`); run from PowerShell 3 or 4 it cannot detect newer syntax, since those versions cannot parse it. [DOC S-z65pkysn]
- The Parser class page describes the parser as returning a `ScriptBlockAst`, tokens and error messages when a script cannot be parsed, and the `ParseFile` and `ParseInput` pages describe parsing only; no Learn page says in so many words that nothing is executed, so "the parser does not run the script" is a reading of what these pages describe. [DER S-k7hdd27i, S-oeqxq56y: the class page's description of its output; no page states non-execution]
- In PowerShell 7.6.6 `ParseFile` reads the file's text, and `ParseFile` and `ParseInput` both tokenize it, build the `ScriptBlockAst`, set `ScriptRequirements` from the tokenizer, then run the post-parse checks (symbol resolution and semantic checks); for a `.schema.psm1` file a source comment says the module is not loaded at parse time. [CODE S-ia7is5xj: engine/parser/Parser.cs#Parser.ParseFile]
- The post-parse checks resolve each `using module` statement at parse time by running `Get-Module -FullyQualifiedName <name> -ListAvailable` (in the current runspace when there is one, else in a new session with only `Get-Module` and the FileSystem provider); a module not found becomes the parse error `ModuleNotFoundDuringParse`. [CODE S-4bjgu6jw: engine/parser/SymbolResolver.cs#SymbolResolver.GetModulesFromUsingModule]
- The classes a `using module` brings in are read by parsing the found module's root script file and collecting its `TypeDefinitionAst` nodes, not by importing the module. [CODE S-vbfv4per: engine/Modules/PSModuleInfo.cs#PSModuleInfo.GetExportedTypeDefinitions]
- `ScriptBlockAst.PerformPostParseChecks` is `SymbolResolver.ResolveSymbols` followed by `SemanticChecks.CheckAst`. [CODE S-ouafwanl: engine/parser/ast.cs#ScriptBlockAst.PerformPostParseChecks]
- Parsing a `configuration` block loads the default DSC CIM keywords during the parse (from the DSC v3 subsystem when it is registered, else `DscClassCache.LoadDefaultCimKeywords`). [CODE S-ia7is5xj: engine/parser/Parser.cs#Parser.ConfigurationStatementRule]
- So the parse path runs none of the parsed script's code, but it is not free of environment lookups: `using module` makes it list available modules and parse the found module's root script, and a `configuration` block loads DSC keywords; a mapper that parses untrusted scripts should expect parse errors for modules the machine lacks, not treat them as broken code. [DER S-ia7is5xj, S-4bjgu6jw, S-vbfv4per, S-ouafwanl: the call path read at v7.6.6; this is implementation, not a documented promise]
- The `DiagnosticRecord` class (PSScriptAnalyzer 1.25.0) has the properties `Message`, `Extent` (an `IScriptExtent`), `RuleName`, `Severity`, `ScriptPath`, the read-only `ScriptName` (the file name part of `ScriptPath`), `RuleSuppressionID`, `SuggestedCorrections` (nullable `IEnumerable<CorrectionExtent>`) and `IsSuppressed`. [CODE S-3olari7o: Engine/Generic/DiagnosticRecord.cs#DiagnosticRecord]
- The custom-rule guide requires a `DiagnosticRecord` to carry at least `Message`, `Extent`, `RuleName` and `Severity`, and says `SuggestedCorrections` has been accepted since PSScriptAnalyzer 1.17.0. [DOC S-62qzauot]
- The `Line` column of the default table view is not a `DiagnosticRecord` property in that class; a script that needs the position reads it from `Extent` (which is an `IScriptExtent`). [DER S-3olari7o, S-yx6xgjzj: the class has no line property; the table view in the Using page shows `Line`]
- `using module <module-name>` takes a module name, a module specification hashtable (`ModuleName` plus one of `ModuleVersion`, `MaximumVersion` or `RequiredVersion`, optional `GUID`) or a path; a relative path resolves against the script that has the statement, and a name or specification is searched in `PSModulePath`. It imports classes and enumerations from the root module, which `Import-Module` and `#Requires` do not. [DOC S-oodal3ol]
- `using namespace <.NET-namespace>` only shortens type names, and `using assembly <path>` loads .NET types from an assembly given as a fully qualified path at the start of execution; a `using` statement must come before any other statement in the script or module, cannot contain a variable, and is not the `Using:` scope modifier. [DOC S-oodal3ol]
- `Import-Module -Name` (position 0, so `Import-Module Example.Tools` names a module) takes module names or file names and does not permit wildcards; without a path the module is looked up in `$Env:PSModulePath`. [DOC S-iass75od]
- A mapper that matches PowerShell code by its module imports therefore reads four places: `#Requires -Modules` and `ScriptRequirements.RequiredModules`, `using module` statements, `Import-Module` command elements found with `FindAll` over `CommandAst` (the first argument, when it is a constant), and manifest `RequiredModules`; a module name held in a variable or built at run time is not visible without executing the script. [DER S-6jyt4xkf, S-oodal3ol, S-iass75od, S-tsdqt57s: the four documented import forms; variables are not `using`-legal and `-Name` takes a string]
- A mapper that must not execute repository code can read a PowerShell repository's pins and public surface from the parser (`ScriptRequirements`, `FindAll` for `FunctionDefinitionAst`) and `Import-PowerShellDataFile` on each `.psd1`, and treat an explicit `FunctionsToExport` list as the module's public commands; a wildcard or missing list leaves the surface known only after an import, which it avoids. [DER S-oeqxq56y, S-ffmai4hf, S-o6gamymj, S-f3ndzkct, S-tsdqt57s, S-jhjw7ppr: the read-only APIs versus the importing commands]

## Reference
- about_Requires: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_requires?view=powershell-7.5
- about_Module_Manifests: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_module_manifests?view=powershell-7.5
- Import-PowerShellDataFile: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/import-powershelldatafile?view=powershell-7.5
- Parser class: https://learn.microsoft.com/en-us/dotnet/api/system.management.automation.language.parser?view=powershellsdk-7.4.0
- Using PSScriptAnalyzer: https://learn.microsoft.com/en-us/powershell/utility-modules/psscriptanalyzer/using-scriptanalyzer
- about_Using: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_using?view=powershell-7.5; Import-Module: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/import-module?view=powershell-7.5
- Creating custom rules: https://learn.microsoft.com/en-us/powershell/utility-modules/psscriptanalyzer/create-custom-rule; DiagnosticRecord source: https://raw.githubusercontent.com/PowerShell/PSScriptAnalyzer/1.25.0/Engine/Generic/DiagnosticRecord.cs
- Parser source (PowerShell v7.6.6): https://raw.githubusercontent.com/PowerShell/PowerShell/v7.6.6/src/System.Management.Automation/engine/parser/Parser.cs; SymbolResolver.cs and ast.cs in the same directory; PSModuleInfo.cs under engine/Modules/
- Related: `agents/codebase-mapping.md` (the same approach across languages); `windows/powershell-7.md` (versions, editions and lifecycle the pins refer to).

## Examples
- SNIPPET: list a script's `#Requires` pins and its function names without running it; context: PowerShell 7.x or 5.1, file `.\Deploy-Example.ps1`; checked: no [DER S-oeqxq56y, S-ffmai4hf, S-o6gamymj: ParseFile, ScriptRequirements and FindAll from their API pages]
```powershell
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\Deploy-Example.ps1), [ref]$tokens, [ref]$errors)
$ast.ScriptRequirements | Select-Object RequiredPSVersion, RequiredPSEditions, RequiredModules, IsElevationRequired
$ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true) | ForEach-Object Name
$errors | Select-Object -ExpandProperty Message
```
- SNIPPET: read a manifest's pins as data; context: PowerShell 5.1 or later; checked: no [DOC S-f3ndzkct]
```powershell
$m = Import-PowerShellDataFile .\ExampleModule.psd1
$m.ModuleVersion; $m.PowerShellVersion; $m.CompatiblePSEditions; $m.RequiredModules; $m.FunctionsToExport
```
