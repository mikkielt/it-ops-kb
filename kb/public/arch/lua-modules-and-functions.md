---
topic: arch/lua-modules-and-functions
priority: P3
applies_to: "Lua 5.4: require and package.loaded, function definitions and local function, call syntax"
retrieved_utc: 2026-10-27
sources: [S-ztiy5c7d]
status: complete
---

# Lua 5.4 modules and function definitions (what a text pattern can read)

## Summary
Lua code loads other modules with `require` and defines functions in two forms, global-style and `local`. Both are
plain statements, so a table of text patterns can find the definitions and the loaded module names without starting
a Lua interpreter. What `require` loads is decided at run time.

## Facts
- `require (modname)` loads a module: when `package.loaded[modname]` already holds a value it returns it, and otherwise it finds a loader through the searchers in `package.searchers`. [DOC S-ztiy5c7d]
- With the default searchers `require` asks `package.preload[modname]` first, then searches for a Lua file along the path in `package.path`. [DOC S-ztiy5c7d]
- `require` calls the loader with the module name and an extra value; a non-nil result is stored in `package.loaded[modname]`, else the entry becomes `true`, and `require` returns that entry plus the loader data. [DOC S-ztiy5c7d]
- `require` raises an error when it cannot load or find a loader for the module. [DOC S-ztiy5c7d]
- A call written `f'string'`, `f"string"` or `f[[string]]` is sugar for `f('string')`, so `require 'util'` and `require('util')` are the same call. [DOC S-ztiy5c7d]
- `function f () body end` is sugar for an assignment to the global `f`, and `function t.a.b.c.f () body end` for `t.a.b.c.f = function () body end`; a function name is a `Name`, optional `.Name` parts and an optional `:Name`. [DOC S-ztiy5c7d]
- `local function f () body end` translates to `local f; f = function () body end`, not to `local f = function () body end`, which matters only when the body refers to `f`. [DOC S-ztiy5c7d]
- Any variable name is global unless declared `local`. [DOC S-ztiy5c7d]
- A text-pattern mapper therefore reads a definition from a line that starts with `function Name` or `local function Name`, an import from `require` followed by a quoted constant (both call forms), and cannot resolve a module name built at run time. [DER S-ztiy5c7d: the grammar and the string-call sugar; a computed name is a value, not text]

## Reference
- Lua 5.4 Reference Manual: https://www.lua.org/manual/5.4/manual.html

## Examples
- SNIPPET: one module import and the two definition forms a pattern table reads; context: Lua 5.4; checked: no [DER S-ztiy5c7d: forms from the manual's grammar]
```lua
local util = require('util')

local function load_map(name)
  return util.read(name)
end

function render(x) return load_map(x) end
```
