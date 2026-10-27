local util = require('util')
local function load_map(name)
  return util.read(name)
end
function render(x) return load_map(x) end
load_map('x')
