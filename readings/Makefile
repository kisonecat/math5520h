all: reading01.pdf reading02.pdf reading03.pdf reading04.pdf reading05.pdf reading06.pdf reading07.pdf reading08.pdf reading09.pdf reading10.pdf reading11.pdf reading12.pdf reading13.pdf reading14.pdf reading15.pdf reading16.pdf reading01.html reading02.html reading03.html reading04.html reading05.html reading06.html reading07.html reading08.html reading09.html reading10.html reading11.html reading12.html reading13.html reading14.html reading15.html reading16.html

%.pdf: %.tex
	pdflatex $<
	pdflatex $<

%.html: %.tex
	pandoc $< -o $@

