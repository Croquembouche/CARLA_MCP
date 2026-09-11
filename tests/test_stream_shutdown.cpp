#include "carla/streaming/detail/tcp/Client.h"
#include <boost/asio/executor_work_guard.hpp>
#include <thread>
#include <vector>
int main(){
 using namespace carla::streaming;
 boost::asio::io_context io;auto guard=boost::asio::make_work_guard(io);
 std::vector<std::thread> threads;
 for(int i=0;i<4;++i)threads.emplace_back([&](){io.run();});
 detail::token_data data{};data.stream_id=2;data.port=19999;data.protocol=detail::token_data::protocol::tcp;
 detail::token_type token(data);token.set_address(boost::asio::ip::make_address("127.0.0.1"));
 for(int i=0;i<2000;++i){
  auto client=std::make_shared<detail::tcp::Client>(io,token,[](carla::Buffer){});
  client->Connect();std::this_thread::yield();client->Stop();client->Stop();
 }
 guard.reset();for(auto &thread:threads)thread.join();
}
