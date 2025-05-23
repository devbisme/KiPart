"""
Test script for random symbol generator
"""

import os
import sys
import argparse
from simp_sexp import Sexp

# Add the parent directory to the path so we can import kipart modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kipart.kipart import empty_symbol_lib, add_quotes
from tests.unit.random_symbol import generate_random_symbol_lib

def main():
    """Generate random symbols based on command-line arguments and save to a file."""
    parser = argparse.ArgumentParser(description="Generate random KiCad symbols for testing")
    parser.add_argument('-n', '--count', type=int, default=1, help="Number of symbols to generate")
    parser.add_argument('-o', '--output', default="random_symbols.kicad_sym", help="Output file name")
    args = parser.parse_args()
    
    # Create a symbol library of random symbols.
    symbol_lib = generate_random_symbol_lib(count=args.count, max_pins=500)
    
    # Add quotes for proper KiCad format
    add_quotes(symbol_lib)
    
    # Write to file
    with open(args.output, 'w') as f:
        f.write(str(symbol_lib))
    
    print(f"Generated {args.count} random symbols and saved to {args.output}")

if __name__ == "__main__":
    main()
