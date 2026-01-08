# Alpine Linux with Rust (via rustup) and Claude Code CLI
FROM hub-mirror.c.163.com/library/alpine:latest

# Install dependencies
RUN apk add --no-cache \
    curl \
    bash \
    git \
    build-base \
    nodejs \
    npm

# Set up Rust mirrors (rsproxy.cn)
ENV RUSTUP_DIST_SERVER="https://rsproxy.cn"
ENV RUSTUP_UPDATE_ROOT="https://rsproxy.cn/rustup"

# Install Rust via rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://rsproxy.cn/rustup-init.sh | sh -s -- -y

# Configure cargo to use rsproxy mirror
RUN mkdir -p /root/.cargo && \
    echo '[source.crates-io]' > /root/.cargo/config.toml && \
    echo 'replace-with = "rsproxy-sparse"' >> /root/.cargo/config.toml && \
    echo '[source.rsproxy-sparse]' >> /root/.cargo/config.toml && \
    echo 'registry = "sparse+https://rsproxy.cn/index/"' >> /root/.cargo/config.toml && \
    echo '[net]' >> /root/.cargo/config.toml && \
    echo 'git-fetch-with-cli = true' >> /root/.cargo/config.toml

# Add cargo to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user
RUN adduser -D -s /bin/bash claude && \
    mkdir -p /home/claude/.claude /home/claude/.cargo && \
    cp /root/.cargo/config.toml /home/claude/.cargo/config.toml && \
    cp -r /root/.rustup /home/claude/.rustup && \
    chown -R claude:claude /home/claude

# Set up Rust for claude user
ENV RUSTUP_HOME="/home/claude/.rustup"
ENV CARGO_HOME="/home/claude/.cargo"
ENV PATH="/home/claude/.cargo/bin:${PATH}"

WORKDIR /workspace
USER claude

CMD ["sleep", "infinity"]
