// Polyfill fetch for the Node.js jest environment
// (Next.js provides this at runtime; we need it in tests)
import { TextEncoder, TextDecoder } from 'util'

global.TextEncoder = TextEncoder
global.TextDecoder = TextDecoder as typeof global.TextDecoder
