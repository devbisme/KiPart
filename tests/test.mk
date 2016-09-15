tests := example1 example2 example3 example4 example5 example6 lt1512 helwig test1
examples := example1 example2 example3 example4 example5 example6

all: $(tests:=.tst)
clean: $(tests:=.clean)
examples: $(examples:=.lib)
tests: $(tests:=.lib)

example1.lib: example1.csv
	kipart $^ -o $@ -w

example2.lib: example1.csv
	kipart $^ -o $@ -w -s num

example3.lib: example1.csv
	kipart $^ -o $@ -w -s name

example4.lib: example1.csv
	kipart $^ -o $@ -w -b

example5.lib: example2.csv
	kipart $^ -o $@ -w -b

example6.lib: example3.csv
	kipart $^ -o $@ -w -b

lt1512.lib: lt1512.csv
	kipart $^ -o $@ -w

test1.lib: test1.csv
	kipart $^ -o $@ -w -s name

helwig.lib: helwig.csv
	kipart $^ -o $@ -w
	
%.tst : %.clean %.lib
	@-diff -qsw "$*.lib" "$* - Copy.lib"
	@sort $*.lib > "$*_sorted.lib"
	@sort "$* - Copy.lib" > "$*_sorted_copy.lib"
	@-diff -qsw "$*_sorted.lib" "$*_sorted_copy.lib"
	@echo "*********************************************************************"
	
%.clean :
	@rm -f $*.lib "$*_sorted.lib" "$*_sorted_copy.lib"
