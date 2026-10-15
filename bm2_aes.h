#pragma once
#include <cstdint>
#include <cstring>
#include "mbedtls/aes.h"

// BM2 broadcasts are exactly one AES-128 CBC block, with a zero IV.
inline bool bm2_aes_cbc_decrypt_16(const uint8_t *key, const uint8_t *iv,
                                  const uint8_t *input, uint8_t *output) {
  mbedtls_aes_context context;
  mbedtls_aes_init(&context);
  uint8_t local_iv[16];
  std::memcpy(local_iv, iv, sizeof(local_iv));
  int result = mbedtls_aes_setkey_dec(&context, key, 128);
  if (result == 0) {
    result = mbedtls_aes_crypt_cbc(&context, MBEDTLS_AES_DECRYPT, 16,
                                 local_iv, input, output);
  }
  mbedtls_aes_free(&context);
  return result == 0;
}
