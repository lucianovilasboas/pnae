from django.test import TestCase

from .tokens import TOKEN_BYTES, generate_token, hash_token


class TokenTests(TestCase):
    def test_token_is_opaque_and_high_entropy(self):
        token = generate_token()
        self.assertIsInstance(token, str)
        self.assertGreaterEqual(len(token), 16)
        self.assertNotEqual(generate_token(), generate_token())

    def test_token_bytes_meets_minimum(self):
        # >= 160 bits de entropia (RN-07).
        self.assertGreaterEqual(TOKEN_BYTES * 8, 160)

    def test_hash_is_deterministic(self):
        token = "token-de-teste"
        self.assertEqual(hash_token(token), hash_token(token))

    def test_hash_differs_per_token(self):
        self.assertNotEqual(hash_token("a"), hash_token("b"))

    def test_empty_token_rejected(self):
        with self.assertRaises(ValueError):
            hash_token("")
