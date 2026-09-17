#pragma once

#include <sys/epoll.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <string>
#include <unordered_map>
#include <vector>
#include <iostream>
#include <cstring>
#include <chrono>
#include <sstream>
#include <algorithm>
#include <functional>
#include <stdexcept>

enum class ConnState {
    ACCEPT,
    READ_REQUEST,
    PARSE_HEADERS,
    FORWARD,
    READ_RESPONSE,
    WRITE_RESPONSE
};

struct ConnectionContext {
    int client_fd = -1;
    int upstream_fd = -1;
    ConnState state = ConnState::ACCEPT;
    std::string read_buffer;
    std::string write_buffer;
    size_t write_offset = 0;
};

struct UpstreamServer {
    std::string host;
    int port;
    int active_requests;
    std::chrono::steady_clock::time_point last_heartbeat;
};

class EpollServer {
public:
    inline EpollServer(int tcp_port, int udp_port) : running(true) {
        epoll_fd = epoll_create1(0);
        if (epoll_fd == -1) {
            throw std::runtime_error("Failed to create epoll file descriptor");
        }
        
        tcp_listen_fd = create_tcp_listener(tcp_port);
        udp_fd = create_udp_socket(udp_port);
        
        struct epoll_event event;
        event.events = EPOLLIN;
        event.data.fd = tcp_listen_fd;
        if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, tcp_listen_fd, &event) == -1) {
            throw std::runtime_error("Failed to add tcp listener to epoll");
        }
        
        event.events = EPOLLIN;
        event.data.fd = udp_fd;
        if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, udp_fd, &event) == -1) {
            throw std::runtime_error("Failed to add udp listener to epoll");
        }
    }
    
    inline ~EpollServer() {
        shutdown();
    }
    
    inline void run() {
        const int MAX_EVENTS = 64;
        struct epoll_event events[MAX_EVENTS];
        
        while (running) {
            int num_events = epoll_wait(epoll_fd, events, MAX_EVENTS, 100);
            if (num_events == -1) {
                if (errno == EINTR) continue;
                break;
            }
            
            for (int i = 0; i < num_events; ++i) {
                int fd = events[i].data.fd;
                
                if (fd == tcp_listen_fd) {
                    handle_new_connection();
                } else if (fd == udp_fd) {
                    handle_udp_heartbeat();
                } else {
                    auto it = connections.find(fd);
                    if (it != connections.end()) {
                        if (events[i].events & (EPOLLERR | EPOLLHUP | EPOLLRDHUP)) {
                            close_connection(fd);
                        } else if (events[i].events & EPOLLIN) {
                            if (fd == it->second.client_fd) {
                                handle_client_data(fd);
                            } else if (fd == it->second.upstream_fd) {
                                handle_upstream_response(fd);
                            }
                        } else if (events[i].events & EPOLLOUT) {
                            if (fd == it->second.upstream_fd && it->second.state == ConnState::FORWARD) {
                                forward_to_upstream(fd);
                            } else if (fd == it->second.client_fd && it->second.state == ConnState::WRITE_RESPONSE) {
                                write_response_to_client(fd);
                            }
                        }
                    }
                }
            }
        }
    }
    
    inline void shutdown() {
        running = false;
        if (tcp_listen_fd != -1) { close(tcp_listen_fd); tcp_listen_fd = -1; }
        if (udp_fd != -1) { close(udp_fd); udp_fd = -1; }
        if (epoll_fd != -1) { close(epoll_fd); epoll_fd = -1; }
        
        for (auto& pair : connections) {
            if (pair.second.client_fd != -1) close(pair.second.client_fd);
            if (pair.second.upstream_fd != -1) close(pair.second.upstream_fd);
        }
        connections.clear();
    }

private:
    int epoll_fd = -1;
    int tcp_listen_fd = -1;
    int udp_fd = -1;
    std::unordered_map<int, ConnectionContext> connections;
    std::vector<UpstreamServer> upstreams;
    bool running;

    inline void make_non_blocking(int fd) {
        int flags = fcntl(fd, F_GETFL, 0);
        if (flags == -1) return;
        fcntl(fd, F_SETFL, flags | O_NONBLOCK);
    }
    
    inline int create_tcp_listener(int port) {
        int fd = socket(AF_INET, SOCK_STREAM, 0);
        if (fd == -1) throw std::runtime_error("TCP socket creation failed");
        
        int opt = 1;
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
        
        make_non_blocking(fd);
        
        struct sockaddr_in addr;
        std::memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = INADDR_ANY;
        addr.sin_port = htons(port);
        
        if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) == -1) {
            throw std::runtime_error("TCP bind failed");
        }
        
        if (listen(fd, SOMAXCONN) == -1) {
            throw std::runtime_error("TCP listen failed");
        }
        
        return fd;
    }
    
    inline int create_udp_socket(int port) {
        int fd = socket(AF_INET, SOCK_DGRAM, 0);
        if (fd == -1) throw std::runtime_error("UDP socket creation failed");
        
        make_non_blocking(fd);
        
        struct sockaddr_in addr;
        std::memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = INADDR_ANY;
        addr.sin_port = htons(port);
        
        if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) == -1) {
            throw std::runtime_error("UDP bind failed");
        }
        
        return fd;
    }
    
    inline void handle_new_connection() {
        while (true) {
            struct sockaddr_in client_addr;
            socklen_t client_len = sizeof(client_addr);
            int client_fd = accept(tcp_listen_fd, (struct sockaddr*)&client_addr, &client_len);
            
            if (client_fd == -1) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) {
                    break;
                }
                continue;
            }
            
            make_non_blocking(client_fd);
            
            struct epoll_event event;
            event.events = EPOLLIN | EPOLLET;
            event.data.fd = client_fd;
            epoll_ctl(epoll_fd, EPOLL_CTL_ADD, client_fd, &event);
            
            ConnectionContext ctx;
            ctx.client_fd = client_fd;
            ctx.state = ConnState::READ_REQUEST;
            connections[client_fd] = ctx;
        }
    }
    
    inline void handle_udp_heartbeat() {
        char buffer[1024];
        struct sockaddr_in sender_addr;
        socklen_t sender_len = sizeof(sender_addr);
        
        while (true) {
            ssize_t n = recvfrom(udp_fd, buffer, sizeof(buffer) - 1, 0, (struct sockaddr*)&sender_addr, &sender_len);
            if (n == -1) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                continue;
            }
            
            buffer[n] = '\0';
            std::string payload(buffer);
            
            size_t port_pos = payload.find("\"port\"");
            size_t req_pos = payload.find("\"active_requests\"");
            
            if (port_pos != std::string::npos && req_pos != std::string::npos) {
                int port = 0;
                int reqs = 0;
                
                size_t p_colon = payload.find(":", port_pos);
                if (p_colon != std::string::npos) {
                    port = std::stoi(payload.substr(p_colon + 1));
                }
                
                size_t r_colon = payload.find(":", req_pos);
                if (r_colon != std::string::npos) {
                    reqs = std::stoi(payload.substr(r_colon + 1));
                }
                
                std::string host = inet_ntoa(sender_addr.sin_addr);
                
                bool found = false;
                for (auto& srv : upstreams) {
                    if (srv.host == host && srv.port == port) {
                        srv.active_requests = reqs;
                        srv.last_heartbeat = std::chrono::steady_clock::now();
                        found = true;
                        break;
                    }
                }
                
                if (!found) {
                    upstreams.push_back({host, port, reqs, std::chrono::steady_clock::now()});
                }
            }
        }
    }
    
    inline void handle_client_data(int fd) {
        char buffer[4096];
        auto& ctx = connections[fd];
        
        while (true) {
            ssize_t n = read(fd, buffer, sizeof(buffer));
            if (n > 0) {
                ctx.read_buffer.append(buffer, n);
            } else if (n == -1) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) {
                    break;
                }
                close_connection(fd);
                return;
            } else {
                close_connection(fd);
                return;
            }
        }
        
        if (ctx.state == ConnState::READ_REQUEST) {
            if (ctx.read_buffer.find("\r\n\r\n") != std::string::npos) {
                ctx.state = ConnState::FORWARD;
                
                UpstreamServer* upstream = select_upstream();
                if (!upstream) {
                    std::string err_resp = "HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n";
                    ctx.write_buffer = err_resp;
                    ctx.state = ConnState::WRITE_RESPONSE;
                    write_response_to_client(fd);
                    return;
                }
                
                connect_upstream(fd, *upstream);
            }
        }
    }
    
    inline UpstreamServer* select_upstream() {
        if (upstreams.empty()) return nullptr;
        
        auto now = std::chrono::steady_clock::now();
        UpstreamServer* best = nullptr;
        
        for (auto& srv : upstreams) {
            if (std::chrono::duration_cast<std::chrono::seconds>(now - srv.last_heartbeat).count() < 30) {
                if (!best || srv.active_requests < best->active_requests) {
                    best = &srv;
                }
            }
        }
        
        return best;
    }
    
    inline void connect_upstream(int client_fd, const UpstreamServer& upstream) {
        auto& ctx = connections[client_fd];
        
        int upstream_fd = socket(AF_INET, SOCK_STREAM, 0);
        if (upstream_fd == -1) {
            close_connection(client_fd);
            return;
        }
        
        make_non_blocking(upstream_fd);
        
        struct sockaddr_in addr;
        std::memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        addr.sin_port = htons(upstream.port);
        inet_pton(AF_INET, upstream.host.c_str(), &addr.sin_addr);
        
        int res = connect(upstream_fd, (struct sockaddr*)&addr, sizeof(addr));
        if (res == -1 && errno != EINPROGRESS) {
            close_connection(client_fd);
            return;
        }
        
        ctx.upstream_fd = upstream_fd;
        connections[upstream_fd] = ctx;
        
        struct epoll_event event;
        event.events = EPOLLIN | EPOLLOUT | EPOLLET;
        event.data.fd = upstream_fd;
        epoll_ctl(epoll_fd, EPOLL_CTL_ADD, upstream_fd, &event);
    }
    
    inline void forward_to_upstream(int fd) {
        auto& ctx = connections[fd];
        
        while (ctx.write_offset < ctx.read_buffer.size()) {
            ssize_t n = write(fd, ctx.read_buffer.data() + ctx.write_offset, ctx.read_buffer.size() - ctx.write_offset);
            if (n > 0) {
                ctx.write_offset += n;
            } else if (n == -1) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                close_connection(fd);
                return;
            }
        }
        
        if (ctx.write_offset == ctx.read_buffer.size()) {
            ctx.state = ConnState::READ_RESPONSE;
            ctx.read_buffer.clear();
            ctx.write_offset = 0;
            
            int client_fd = ctx.client_fd;
            connections[client_fd].state = ConnState::READ_RESPONSE;
            connections[client_fd].read_buffer.clear();
        }
    }
    
    inline void handle_upstream_response(int fd) {
        char buffer[4096];
        auto& ctx = connections[fd];
        
        while (true) {
            ssize_t n = read(fd, buffer, sizeof(buffer));
            if (n > 0) {
                ctx.write_buffer.append(buffer, n);
            } else if (n == -1) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                close_connection(fd);
                return;
            } else {
                break; // EOF
            }
        }
        
        if (!ctx.write_buffer.empty()) {
            ctx.state = ConnState::WRITE_RESPONSE;
            int client_fd = ctx.client_fd;
            connections[client_fd].write_buffer = ctx.write_buffer;
            connections[client_fd].state = ConnState::WRITE_RESPONSE;
            
            struct epoll_event event;
            event.events = EPOLLIN | EPOLLOUT | EPOLLET;
            event.data.fd = client_fd;
            epoll_ctl(epoll_fd, EPOLL_CTL_MOD, client_fd, &event);
            
            write_response_to_client(client_fd);
        }
    }
    
    inline void write_response_to_client(int fd) {
        auto& ctx = connections[fd];
        
        while (ctx.write_offset < ctx.write_buffer.size()) {
            ssize_t n = write(fd, ctx.write_buffer.data() + ctx.write_offset, ctx.write_buffer.size() - ctx.write_offset);
            if (n > 0) {
                ctx.write_offset += n;
            } else if (n == -1) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                close_connection(fd);
                return;
            }
        }
        
        if (ctx.write_offset == ctx.write_buffer.size()) {
            close_connection(fd);
        }
    }
    
    inline void close_connection(int fd) {
        auto it = connections.find(fd);
        if (it != connections.end()) {
            int client_fd = it->second.client_fd;
            int upstream_fd = it->second.upstream_fd;
            
            if (client_fd != -1) {
                epoll_ctl(epoll_fd, EPOLL_CTL_DEL, client_fd, nullptr);
                close(client_fd);
                connections.erase(client_fd);
            }
            if (upstream_fd != -1) {
                epoll_ctl(epoll_fd, EPOLL_CTL_DEL, upstream_fd, nullptr);
                close(upstream_fd);
                connections.erase(upstream_fd);
            }
        }
    }
};
