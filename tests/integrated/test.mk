tests := example1 example2 example3 example4 example5 example6 example7 lt1512 helwig test1 hidden_test stm32_test
examples := example1 example2 example3 example4 example5 example6 example7

#all: randomtest
all: randomtest1 randomtest2 randomtest3 $(tests:=.tst)
clean: randomtest_clean $(tests:=.clean)
examples: $(examples:=.lib)
tests: $(tests:=.tst)

FLAGS= -s num --box_line_width 12 --fill no_fill

kilib2csv:
	@kilib2csv -w -o v6.csv 4xxx.kicad_sym
	@kipart -w v6.csv
	@kilib2csv -w -o v5.csv v6.lib
	@# Cut out unit fields since V5 & V6 are different.
	@cut -d , -f 1-4,6- v5.csv > v5_no_units.csv
	@cut -d , -f 1-4,6- v6.csv > v6_no_units.csv
	@/bin/diff -s v5_no_units.csv v6_no_units.csv
	@echo "*********************************************************************"

randomtest1:
	@python random_csv.py > randomtest.csv
	@kipart $(FLAGS) randomtest.csv -o randomtest.lib -w
	@kilib2csv randomtest.lib -o randomtest2.csv -w
	@/bin/diff -s randomtest.csv randomtest2.csv
	@echo "*********************************************************************"

randomtest2:
	@python random_csv.py > randomtest1.csv
	@python random_csv.py > randomtest2.csv
	@kipart $(FLAGS) randomtest1.csv randomtest2.csv -o randomtest.lib -w
	@/bin/sort -u randomtest.lib > randomtest_sorted.lib
	@kipart $(FLAGS) randomtest1.csv randomtest2.csv -w
	@cat randomtest1.lib randomtest2.lib > randomtest3.lib
	@/bin/sort -u randomtest3.lib > randomtest3_sorted.lib
	@/bin/diff -s randomtest_sorted.lib randomtest3_sorted.lib
	@echo "*********************************************************************"

randomtest3:
	@python random_csv.py > randomtest1.csv
	@python random_csv.py > randomtest2.csv
	@kipart $(FLAGS) randomtest1.csv randomtest2.csv -w
	@kilib2csv randomtest1.lib -o randomtest1_rebuilt.csv -w
	@kilib2csv randomtest2.lib -o randomtest2_rebuilt.csv -w
	@/bin/diff -s randomtest1.csv randomtest1_rebuilt.csv
	@/bin/diff -s randomtest2.csv randomtest2_rebuilt.csv
	@echo "*********************************************************************"

randomtest_clean:
	@rm -f randomtest*.csv randomtest*.lib

example1.lib: example1.csv
	kipart $(FLAGS) $^ -o $@ -w

example2.lib: example1.csv
	kipart $(FLAGS) $^ -o $@ -w -s num

example3.lib: example1.csv
	kipart $(FLAGS) $^ -o $@ -w -s name

example4.lib: example1.csv
	kipart $(FLAGS) $^ -o $@ -w -b

example5.lib: example2.csv
	kipart $(FLAGS) $^ -o $@ -w -b

example6.lib: example3.csv
	kipart $(FLAGS) $^ -o $@ -w -b

example7.lib: example1.xlsx
	kipart $(FLAGS) $^ -o $@ -w

lt1512.lib: lt1512.csv
	kipart $(FLAGS) $^ -o $@ -w

test1.lib: test1.csv
	kipart $(FLAGS) $^ -o $@ -w -s name

helwig.lib: helwig.csv
	kipart $(FLAGS) $^ -o $@ -w

hidden_test.lib: hidden_test.csv
	kipart $(FLAGS) $^ -o $@ -w

stm32_test.lib: stm32_test.csv
	kipart $(FLAGS) -r stm32cube $^ -w

%.tst : %.clean %.lib
	@/bin/diff -qsw "$*.lib" "$* - Copy.lib"
	@sort $*.lib > "$*_sorted.lib"
	@sort "$* - Copy.lib" > "$*_sorted_copy.lib"
	@/bin/diff -qsw "$*_sorted.lib" "$*_sorted_copy.lib"
	@echo "*********************************************************************"

%.clean :
	@rm -f $*.lib "$*_sorted.lib" "$*_sorted_copy.lib" xlsx_to_csv_file.csv v[56]*.*
