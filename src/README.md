# Source Modules


| Module                    | Purpose                                                  |
| ------------------------- | -------------------------------------------------------- |
| [chunking](chunking/)     | Tree-sitter parsing and semantic code chunking           |
| [cli](cli/)               | Click-based command-line interface                       |
| [core](core/)             | Config, domain models, file locking, timing, utilities   |
| [embedding](embedding/)   | Embedder abstraction (local ONNX via fastembed)         |
| [graph](graph/)           | Code relationship graph (calls, imports, inheritance)    |
| [mcp_server](mcp_server/) | MCP server for AI assistant integration                  |
| [pipeline](pipeline/)     | Index build/update orchestration and file watcher        |
| [retrieval](retrieval/)   | Search orchestration and structural boosting             |
| [skeleton](skeleton/)     | File skeleton extraction (signatures, no bodies)         |
| [state](state/)           | Index metadata state machine and schema versioning       |
| [storage](storage/)       | LanceDB vector store                                     |
| [vcs](vcs/)               | Git integration (file discovery, diff, branch detection) |


