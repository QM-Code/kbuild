#include <alpha/sdk.hpp>
#include <beta/sdk.hpp>
#include <gamma/sdk.hpp>
#include <{{PROJECT_ID}}.hpp>

#include <iostream>

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;

    {{PROJECT_ID}}::demo::alpha::EmitDemoOutput();
    {{PROJECT_ID}}::demo::beta::EmitDemoOutput();
    {{PROJECT_ID}}::demo::gamma::EmitDemoOutput();

    std::cout << "{{PROJECT_ID_UPPER}} demo {{DEMO_TITLE_LOWER}} compile/link/integration check passed\\n";
    return 0;
}
