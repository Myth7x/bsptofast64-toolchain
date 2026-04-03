add_executable(vtf2png main.cpp)

target_compile_features(vtf2png PRIVATE cxx_std_23)

find_package(Threads REQUIRED)
target_link_libraries(vtf2png PRIVATE VTFLib13 Threads::Threads)
target_include_directories(vtf2png PRIVATE
    ${vtflib_SOURCE_DIR}/src
    ${vtflib_BINARY_DIR}/src
    ${stb_SOURCE_DIR}
)
