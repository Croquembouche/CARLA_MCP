// Same ROS bag writer and storage plugin, with blocking native I/O off the GIL.
#include <pybind11/pybind11.h>
#include <rosbag2_cpp/writer.hpp>
#include <rosbag2_storage/ros_helper.hpp>
#include <rosbag2_storage/storage_options.hpp>
#include <rosbag2_storage/topic_metadata.hpp>
#include <memory>
#include <string>
#include <stdexcept>
#include <fastcdr/Cdr.h>
#include <fastcdr/FastBuffer.h>
#include <vector>
#include <cstring>
#include <limits>

namespace py = pybind11;

class BagWriter {
  std::unique_ptr<rosbag2_cpp::Writer> writer;
public:
  explicit BagWriter(const std::string & path) {
    writer = std::make_unique<rosbag2_cpp::Writer>();
    rosbag2_storage::StorageOptions storage;
    storage.uri = path;
    storage.storage_id = "sqlite3";
    storage.max_cache_size = 0; // Backpressure is implemented by the Python owner.
    rosbag2_cpp::ConverterOptions converter;
    converter.input_serialization_format = "cdr";
    converter.output_serialization_format = "cdr";
    writer->open(storage, converter);
  }
  void create_topic(const std::string & name, const std::string & type) {
    if (!writer) throw std::runtime_error("Bag is closed");
    rosbag2_storage::TopicMetadata topic;
    topic.name = name;
    topic.type = type;
    topic.serialization_format = "cdr";
    writer->create_topic(topic);
  }
  void write(const std::string & topic, const py::bytes & bytes, int64_t timestamp) {
    if (!writer) throw std::runtime_error("Bag is closed");
    char * data = nullptr;
    Py_ssize_t size = 0;
    if (PyBytes_AsStringAndSize(bytes.ptr(), &data, &size) != 0) throw py::error_already_set();
    // The argument owns an immutable Python buffer throughout this call.
    // Copy directly into ROS-owned storage, avoiding a temporary std::string.
    // Reacquire the GIL before the Python argument can be decref'd.
    py::gil_scoped_release release;
    auto message = std::make_shared<rosbag2_storage::SerializedBagMessage>();
    message->topic_name = topic;
    message->serialized_data = rosbag2_storage::make_serialized_message(data, size);
    message->time_stamp = timestamp;
    writer->write(message);
  }
  void close() {
    if (writer) writer->close();
    writer.reset();
  }
};

// Serialize the standard sensor_msgs/Image wire format without materializing
// a Python byte array and a second ROS C message containing the same pixels.
// Fast-CDR owns the alignment/encapsulation rules; only the final octet sequence
// is copied directly into the immutable Python result.
py::bytes serialize_image(int32_t sec,uint32_t nanosec,const std::string& frame,
    uint32_t height,uint32_t width,const std::string& encoding,uint8_t bigendian,
    uint32_t step,const py::bytes& pixels) {
  char* data=nullptr;Py_ssize_t size=0;
  if(PyBytes_AsStringAndSize(pixels.ptr(),&data,&size)!=0)throw py::error_already_set();
  if(nanosec>=1000000000u || bigendian>1 || uint64_t(height)*step!=uint64_t(size) ||
      uint64_t(size)>std::numeric_limits<uint32_t>::max())
    throw std::invalid_argument("Invalid Image timestamp, byte order, or payload size");
  if(frame.find('\0')!=std::string::npos || encoding.find('\0')!=std::string::npos ||
      frame.size()>=std::numeric_limits<uint32_t>::max() || encoding.size()>=std::numeric_limits<uint32_t>::max())
    throw std::invalid_argument("Invalid Image string");
  std::vector<char> header(frame.size()+encoding.size()+128,0);
  eprosima::fastcdr::FastBuffer buffer(header.data(),header.size());
  eprosima::fastcdr::Cdr cdr(buffer,eprosima::fastcdr::Cdr::LITTLE_ENDIANNESS,eprosima::fastcdr::Cdr::DDS_CDR);
  cdr.serialize_encapsulation();
  cdr << sec << nanosec << frame << height << width << encoding << bigendian << step << uint32_t(size);
  const size_t header_size=cdr.getSerializedDataLength();
  if(uint64_t(size)+header_size>uint64_t(PY_SSIZE_T_MAX))throw std::length_error("Image too large");
  PyObject* object=PyBytes_FromStringAndSize(nullptr,Py_ssize_t(header_size)+size);
  if(!object)throw py::error_already_set();
  auto result=py::reinterpret_steal<py::bytes>(object);
  char* output=PyBytes_AS_STRING(object);
  {
    py::gil_scoped_release release;
    std::memcpy(output,header.data(),header_size);
    if(size)std::memcpy(output+header_size,data,size);
  }
  return result;
}

PYBIND11_MODULE(_bag_native, module) {
  module.def("serialize_image",&serialize_image);
  py::class_<BagWriter>(module, "BagWriter")
    .def(py::init<const std::string &>(), py::call_guard<py::gil_scoped_release>())
    .def("create_topic", &BagWriter::create_topic, py::call_guard<py::gil_scoped_release>())
    .def("write", &BagWriter::write)
    .def("close", &BagWriter::close, py::call_guard<py::gil_scoped_release>());
}
