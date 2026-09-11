#include "carla/streaming/low_level/Client.h"
#include <cassert>
#include <map>
#include <string>

struct FakeStream {
  using protocol_type = boost::asio::ip::tcp;
  static std::map<unsigned,int> stopped;
  unsigned port;
  template<class Callback> FakeStream(boost::asio::io_context&,carla::streaming::detail::token_type token,Callback&&):port(token.get_port()){}
  void Connect(){}
  void Stop(){++stopped[port];}
};
std::map<unsigned,int> FakeStream::stopped;
int main(){
  using namespace carla::streaming;
  boost::asio::io_context io;
  detail::token_data a{};a.stream_id=2;a.port=2011;a.protocol=detail::token_data::protocol::tcp;
  detail::token_type first(a);first.set_address(boost::asio::ip::make_address("127.0.0.1"));
  a.port=2021;detail::token_type second(a);second.set_address(boost::asio::ip::make_address("127.0.0.1"));
  low_level::Client<FakeStream> client;
  client.Subscribe(io,first,[](carla::Buffer){});
  client.Subscribe(io,second,[](carla::Buffer){});
  client.UnSubscribe(second);
  assert(FakeStream::stopped[2021]==1 && FakeStream::stopped[2011]==0);
  client.UnSubscribe(first);
  assert(FakeStream::stopped[2011]==1);
  client.UnSubscribe(first);assert(FakeStream::stopped[2011]==1);
}
