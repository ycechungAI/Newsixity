# Windows x86 Build Guide for Newsixity

## System Requirements

- **OS**: Windows 7 or later
- **Rust**: 1.70+ (installed via rustup)
- **Visual Studio**: Build Tools 2019/2022 with C++ workload
- **Node.js**: 16+ LTS

## Step 1: Install Rust x86 Target

Open PowerShell/CMD as Administrator and run:

```bash
rustup target add i686-pc-windows-msvc
rustup show  # Verify i686-pc-windows-msvc is installed
```

## Step 2: Verify Visual Studio Build Tools

Ensure the **Visual Studio C++ Build Tools** include x86 support:
- Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
- During installation, select "Desktop development with C++"
- Make sure "Windows 10 SDK" and "C++ CMake tools" are checked

Verify MSVC is available:
```bash
"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86
```

## Step 3: Build Frontend Assets

From the project root:

```bash
npm install
npm run build
```

This generates optimized frontend assets in `dist/`.

## Step 4: Build Tauri App for x86

```bash
cd src-tauri
cargo build --release --target i686-pc-windows-msvc
```

**Build time**: 3-10 minutes (first build takes longer due to dependencies).

## Output

The compiled executable will be at:
```
src-tauri/target/i686-pc-windows-msvc/release/newsixity.exe
```

## Bundle for Distribution (Optional)

To create an MSI installer:

```bash
cd src-tauri
cargo tauri build --target i686-pc-windows-msvc
```

Output: `src-tauri/target/i686-pc-windows-msvc/release/bundle/msi/`

## Troubleshooting

### Linker Errors
If you get "linker not found" errors:
1. Run `vcvarsall.bat` to set up MSVC environment
2. Ensure Visual Studio Build Tools are installed

### Target Not Found
```bash
rustup target add i686-pc-windows-msvc
rustup update
```

### Clean Build
If something breaks:
```bash
cargo clean
cargo build --release --target i686-pc-windows-msvc
```

### Check Configuration

Your current `Cargo.toml` is optimized for release:
- LTO: enabled (smaller binary)
- Panic: abort (faster)
- Codegen units: 1 (better optimization)

## Tauri Version
Current: v2 (latest with improved Windows x86 support)

## Next Steps

1. Test the x86 binary on 32-bit systems
2. For automated builds, integrate into CI/CD (GitHub Actions example below)

### GitHub Actions CI/CD (Optional)

Add `.github/workflows/build-x86.yml`:

```yaml
name: Build Windows x86

on: [push, pull_request]

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
          target: i686-pc-windows-msvc
      - uses: actions/setup-node@v4
        with:
          node-version-file: .nvmrc
      - run: npm install
      - run: npm run build
      - run: cd src-tauri && cargo build --release --target i686-pc-windows-msvc
      - uses: actions/upload-artifact@v3
        with:
          name: newsixity-x86
          path: src-tauri/target/i686-pc-windows-msvc/release/newsixity.exe
```
