# .latexmkrc — latexmk configuration
# Output PDF to ../../build/ instead of local directory

$pdf_mode = 1;           # Use pdflatex
$pdf_previewer = 'zathura %O %S'; # Preview with zathura
$out_dir = '../build';   # Output directory
$aux_dir = '../build/latex-aux'; # Auxiliary files

# Clean up auxiliary files after successful PDF generation
$clean_ext = "fls fdb_latexmk";
