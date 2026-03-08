#include <{{LIBRARY_ID}}/sdk.hpp>

#include <{{PROJECT_ID}}.hpp>

#include <iostream>

namespace {

bool g_initialized = false;

} // namespace

namespace {{PROJECT_ID}}::demo::{{LIBRARY_ID}} {

void Initialize() {
    if (!g_initialized) {
        g_initialized = true;
    }
}

void EmitDemoOutput() {
    Initialize();
    std::cout << "[{{LIBRARY_ID}}] demo sdk initialized\\n";
}

} // namespace {{PROJECT_ID}}::demo::{{LIBRARY_ID}}
