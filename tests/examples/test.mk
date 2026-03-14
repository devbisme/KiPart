tests := example1 example2 example3 example4 helwig hidden_test hyozd lt1512 multi_sides pin_length property_test spaces_test test1 74hc_logic dram dual_opamp mixed_types opa2277 rt9818

all: $(tests:=.tst)

clean: $(tests:=.clean)

# This prevents .kicad_Sym files from being removed after they're made.
.SECONDARY:

FLAGS= -b

%.kicad_sym: %.sdt
	sdt2csv $^ | kipart -w -o $@

%.kicad_sym: %.csv
	kipart $(FLAGS) $^ -o $@ -w

%.tst : %.kicad_sym
	@echo "*********************************************************************"

%.clean : %.kicad_sym
	@echo "Cleaning up $^"
	@rm -f $^
