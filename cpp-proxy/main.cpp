#include "epoll_server.hpp"
#include <csignal>
#include <iostream>

static EpollServer* g_server = nullptr;

void signal_handler(int sig) {
    std::cout << "\nReceived signal " << sig << ", shutting down...\n";
    if (g_server) g_server->shutdown();
    exit(0);
}

int main() {
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);
    
    try {
        EpollServer server(8080, 8081);
        g_server = &server;
        std::cout << "[Gateway Proxy] TCP listening on port 8080" << std::endl;
        std::cout << "[Gateway Proxy] UDP heartbeat receiver on port 8081" << std::endl;
        std::cout << "[Gateway Proxy] Waiting for connections..." << std::endl;
        server.run();
    } catch (const std::exception& e) {
        std::cerr << "Fatal: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}
