add_executable(bsp2obj
    main.cpp
    bsp_reader.cpp
)

target_compile_features(bsp2obj PRIVATE cxx_std_23)

find_package(Threads REQUIRED)
target_link_libraries(bsp2obj PRIVATE Threads::Threads)
