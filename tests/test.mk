tests := example1 example2 example3 example4 example5 example6 lt1512 helwig test1 hidden_test
examples := example1 example2 example3 example4 example5 example6

#all: randomtest
all: randomtest1 randomtest2 randomtest3 $(tests:=.tst)
clean: randomtest_clean $(tests:=.clean)
examples: $(examples:=.lib)
tests: $(tests:=.tst)

randomtest1:
	@python random_csv.py > randomtest.csv
	@kipart randomtest.csv -o randomtest.lib -w
	@kilib2csv randomtest.lib -o randomtest2.csv -w
	@-/bin/diff -s randomtest.csv randomtest2.csv
	@echo "*********************************************************************"

randomtest2:
	@python random_csv.py > randomtest1.csv
	@python random_csv.py > randomtest2.csv
	@kipart randomtest1.csv randomtest2.csv -o randomtest.lib -w
	@-/bin/sort -u randomtest.lib > randomtest_sorted.lib
	@kipart randomtest1.csv randomtest2.csv -w
	@cat randomtest1.lib randomtest2.lib > randomtest3.lib
	@-/bin/sort -u randomtest3.lib > randomtest3_sorted.lib
	@-/bin/diff -s randomtest_sorted.lib randomtest3_sorted.lib
	@echo "*********************************************************************"

randomtest3:
	@python random_csv.py > randomtest1.csv
	@python random_csv.py > randomtest2.csv
	@kipart randomtest1.csv randomtest2.csv -w
	@kilib2csv randomtest1.lib -o randomtest1_rebuilt.csv -w
	@kilib2csv randomtest2.lib -o randomtest2_rebuilt.csv -w
	@-/bin/diff -s randomtest1.csv randomtest1_rebuilt.csv
	@-/bin/diff -s randomtest2.csv randomtest2_rebuilt.csv
	@echo "*********************************************************************"

randomtest_clean:
	@rm -f randomtest*.csv randomtest*.lib

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

hidden_test.lib: hidden_test.csv
	kipart $^ -o $@ -w

%.tst : %.clean %.lib
	@-/bin/diff -qsw "$*.lib" "$* - Copy.lib"
	@sort $*.lib > "$*_sorted.lib"
	@sort "$* - Copy.lib" > "$*_sorted_copy.lib"
	@-/bin/diff -qsw "$*_sorted.lib" "$*_sorted_copy.lib"
	@echo "*********************************************************************"

%.clean :
	@rm -f $*.lib "$*_sorted.lib" "$*_sorted_copy.lib"
