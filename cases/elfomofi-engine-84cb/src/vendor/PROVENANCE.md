# Math dependency

`Math.sol` is the unchanged OpenZeppelin Contracts v4.9.6 file from
[the tagged repository](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/v4.9.6/contracts/utils/math/Math.sol).
The adjacent `OpenZeppelin-LICENSE` preserves its MIT license.

SHA-256: `85a2caf3bd06579fb55236398c1321e15fd524a8fe140dff748c0f73d7a52345`.

This library was selected to reproduce observed arithmetic and error behavior.
Its inclusion does not establish the original engine's dependency version.

`src/EngineState.sol` also contains `fullMulDiv`, adapted from that MIT-licensed
implementation. It uses an empty revert when the denominator is zero or the
512-bit quotient would overflow, and an assembly `div` in the non-overflow path.
Those changes reproduce the recovered engine routine. The vendored `Math.sol`
itself remains unchanged; the same adjacent license covers the adapted code.
