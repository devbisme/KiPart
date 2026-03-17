tests := example1 example2 example3 example4 helwig hidden_test hyozd lt1512 multi_sides pin_length property_test spaces_test test1 grabbag

all: $(tests:=.tst)

clean: $(tests:=.clean)

# This prevents .kicad_sym files from being removed after they're made.
.SECONDARY:

FLAGS= -b

%.kicad_sym: %.spd
	spd2csv $^ | kipart -w -o $@

%.kicad_sym: %.csv
	kipart $(FLAGS) $^ -o $@ -w

%.tst : %.kicad_sym
	@echo "*********************************************************************"

%.clean : %.kicad_sym
	@echo "Cleaning up $^"
	@rm -f $^
