using System.Security.Cryptography;
using System.Text;

namespace Api.Embeddings;

public class HashingEmbeddingProvider(int dims = 256) : IEmbeddingProvider
{
    /*
     * Objetivos: 
     * 1) Convertir texto a un vector numerico para medir la similitud para buscar productos parecidos
     * 2) Hacer un RAG light rankeando documentos por consulta
     * 3) En produccion podria ser reemplazado por un AzureOpenAIEmbeddingProvider
     */
    private readonly int _dims = dims;

    public float[] Embed(string text)
    {
        var vec = new float[_dims];
        foreach (var tok in Tokenize(text))
        {
            var idx = HashToIndex(tok, _dims);
            vec[idx] += 1f;
        }
        // L2 normalize
        var norm = MathF.Sqrt(vec.Sum(v => v * v)) + 1e-6f;
        for (int i = 0; i < vec.Length; i++) vec[i] /= norm;
        return vec;
    }

    private static IEnumerable<string> Tokenize(string t) =>
        t.ToLowerInvariant().Split(new[] { ' ', ',', '.', '-', '/', '_' }, StringSplitOptions.RemoveEmptyEntries);

    private static int HashToIndex(string s, int mod)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(s));
        return BitConverter.ToInt32(bytes, 0) & 0x7fffffff % mod;
    }
}
