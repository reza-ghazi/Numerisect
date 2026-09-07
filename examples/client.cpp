// SPDX-License-Identifier: GPL-3.0-or-later
// Numerisect API from C++ with libcurl:  g++ -std=c++17 client.cpp -lcurl -o client
#include <curl/curl.h>
#include <iostream>
#include <string>

static size_t collect(void *data, size_t size, size_t count, void *userp) {
  static_cast<std::string *>(userp)->append(static_cast<char *>(data), size * count);
  return size * count;
}

int main() {
  const std::string base = "http://127.0.0.1:8765";
  curl_global_init(CURL_GLOBAL_DEFAULT);
  CURL *curl = curl_easy_init();
  std::string session;

  // 1. Obtain the per-launch session token (stored in a cookie jar in memory).
  curl_easy_setopt(curl, CURLOPT_URL, (base + "/api/session").c_str());
  curl_easy_setopt(curl, CURLOPT_COOKIEFILE, "");
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, collect);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &session);
  curl_easy_perform(curl);

  // 2. Call a protected route reusing the same handle, so the cookie is replayed.
  std::string body;
  const std::string payload = R"({"expression":"32416190071","mode":"proven"})";
  struct curl_slist *headers = curl_slist_append(nullptr, "Content-Type: application/json");
  curl_easy_setopt(curl, CURLOPT_URL, (base + "/api/primes/check").c_str());
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload.c_str());
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
  curl_easy_perform(curl);
  std::cout << body << std::endl;

  curl_slist_free_all(headers);
  curl_easy_cleanup(curl);
  curl_global_cleanup();
  return 0;
}
