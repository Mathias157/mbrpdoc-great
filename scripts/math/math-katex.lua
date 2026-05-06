-- Pandoc Lua filter: render math via KaTeX in HTML/PDF output.
-- Trivial passthrough; weasyprint + KaTeX CSS handles rendering.

function Math(elem)
  return elem
end
