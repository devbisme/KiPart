tests := example1 example2 example3 example4 helwig hidden_test hyozd lt1512 multi_sides pin_length spaces_test test1

all: $(tests:=.tst)

clean: $(tests:=.clean)

# This prevents .kicad_Sym files from being removed after they're made.
.SECONDARY:

FLAGS= -s num --ccw

%.kicad_sym: %.csv
	kipart $(FLAGS) $^ -o $@ -w

%.tst : %.kicad_sym
	@echo "*********************************************************************"

%.clean : %.kicad_sym
	@echo "Cleaning up $^"
	@rm -f $^
