vcpkg_from_github(
    OUT_SOURCE_PATH SOURCE_PATH
    REPO cliquot22/TheiaMCR_C
    REF "v${VERSION}"
    SHA512 b7225cbbfa275ea183a36e34434d5b1db40a7a3a18907c7fc5ba1b55ecbe07a3dd3d2f1a08b7823a883f2622bbb91a0f1d13f5e082a58e0fee874f90285c8ee3
    HEAD_REF main
)

vcpkg_check_features(OUT_FEATURE_OPTIONS FEATURE_OPTIONS
    FEATURES
        python ENABLE_PYTHON_BINDINGS
)

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    OPTIONS
        ${FEATURE_OPTIONS}
)

vcpkg_cmake_install()

file(INSTALL "${SOURCE_PATH}/LICENSE" DESTINATION "${CURRENT_PACKAGES_DIR}/share/${PORT}" RENAME copyright)

# Install headers
vcpkg_copy_pdbs()
