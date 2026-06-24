"""
Small built-in keyword taxonomy for deriving languages + topics from free text.

Deliberately tiny and explainable — no embeddings, no LLM. Each canonical label
maps to a set of keyword aliases; we match those aliases as whole words against a
developer's cleaned text blob.
"""

# canonical language -> alias keywords (matched as whole words, lowercased)
LANGUAGES: dict[str, list[str]] = {
    "python": ["python", "py", "django", "flask", "fastapi", "pandas", "numpy"],
    "rust": ["rust", "rustlang", "cargo", "tokio", "crate"],
    "go": ["go", "golang", "goroutine"],
    "javascript": ["javascript", "js", "node", "nodejs", "npm"],
    "typescript": ["typescript", "ts", "tsx"],
    "c": ["c", "clang", "ansi-c"],
    "cpp": ["cpp", "c++", "cplusplus"],
    "java": ["java", "jvm", "spring"],
    "ruby": ["ruby", "rails"],
    "php": ["php", "laravel"],
    "swift": ["swift", "swiftui"],
    "kotlin": ["kotlin"],
    "haskell": ["haskell", "ghc"],
    "elixir": ["elixir", "erlang"],
    "zig": ["zig"],
}

# canonical topic -> alias keywords
TOPICS: dict[str, list[str]] = {
    "web": ["web", "frontend", "backend", "http", "html", "css", "browser", "server"],
    "ml": ["ml", "machine learning", "ai", "neural", "model", "training", "tensor"],
    "devops": ["devops", "docker", "kubernetes", "k8s", "ci", "cd", "terraform"],
    "parsing": ["parser", "parsing", "lexer", "tokenizer", "grammar", "compiler"],
    "async": ["async", "concurrency", "concurrent", "await", "futures", "executor"],
    "kernel": ["kernel", "driver", "syscall", "embedded", "firmware", "bootloader"],
    "database": ["database", "db", "sql", "postgres", "sqlite", "query", "storage"],
    "cli": ["cli", "terminal", "command-line", "tui", "shell"],
    "networking": ["network", "networking", "tcp", "socket", "protocol", "packet"],
    "security": ["security", "crypto", "cryptography", "auth", "encryption", "tls"],
    "graphics": ["graphics", "rendering", "shader", "opengl", "vulkan", "gpu"],
    "games": ["game", "gamedev", "engine", "physics"],
}

# Topics that signal genuine depth -> bump toward "advanced".
ADVANCED_TOPICS = {"kernel", "parsing", "async", "security", "graphics"}

# Words that signal a learner -> bias toward "beginner".
BEGINNER_KEYWORDS = {
    "hello", "first", "learning", "learn", "tutorial", "beginner",
    "practice", "todo", "my-first", "starter", "intro", "playground",
}
