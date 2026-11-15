# Reaching an exact executable match

The [current ElfomoFi case](../cases/elfomofi-engine-84cb/README.md) has an exact
24,447-byte parent executable match and a 4,364-byte constructor-prefix match.
Its embedded helper still differs. This checkpoint illustrates why behavioral
agreement, local function similarity and whole-contract equality are separate
results.

## Preserve a tested source checkpoint

Keep the exact Standard JSON input and compiler version. Compile with a stock
compiler, record source hashes, and retain the best tested input while trying
alternatives. Do not patch bytecode or use an opcode payload in a constructor
and describe that as recovered source. A candidate with the right length can
still have different instructions throughout.

## Test source structure as well as arithmetic

Equivalent source expressions can compile differently. In this case:

- Keeping a capacity parameter unchanged and mutating a local `remaining`
  produced the recovered stack lifetimes in two depth routines. The local's
  declaration position also mattered.
- Selecting a storage reference before copying a struct avoided duplicate
  storage reads in the generated trade-statistics helper.
- Narrow exponent types, operand order and the order of checked intermediate
  calculations affected constant reuse and panic-helper placement.
- Small validation and conversion wrappers affected utility emission order
  without changing the external ABI. Applying a wrapper at every similar call
  site could undo a match at a previously recovered site.

These are measured properties of this compiler/input combination, not universal
Solidity style rules or evidence of the author's original source. Names of
reconstructed functions remain analytical labels. Constructed selector
collisions are recorded and independently hashed.

## Establish complete byte equality

Disassembly alignment and normalized jump destinations can locate differences.
They do not prove equality. Local comparisons must include called utility blocks,
constants and fallthrough paths. Ultimately compare the whole executable.

For contracts with immutables, execute the reconstructed constructor with the
captured arguments and dependency fixture, then compare its returned runtime.
A zero-filled runtime template alone does not establish immutable correctness.
State witnesses and synthetic native-call fixtures have their own limits; retain
those qualifications even when the executable comparison succeeds.

## Account for embedded contracts and metadata

Solidity creation code can contain more than the parent constructor and runtime.
The ElfomoFi constructor embeds and creates a second contract. Matching the
parent runtime did not resolve that child's cleanup sequence.

The case's [creation comparison](../cases/elfomofi-engine-84cb/creation_comparison.py)
checks that its ordered regions reconstruct **every byte** of both creation
inputs. It compares both constructor prefixes, both executable runtime regions,
and both recognized terminal CBOR metadata regions separately. It also checks
the parent after constructor execution. Only the identified metadata is excluded
from the executable claim; the unresolved helper bytes remain a reported failure.

Keep explorer acceptance separate from local equality. Original metadata hashes,
source filenames, identifiers and build settings are not recovered merely by
finding a different source input that produces matching executable code.
