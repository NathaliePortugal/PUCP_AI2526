using Api.Domain;

namespace Api.Services
{
    public class PromptTemplateService
    {
        private readonly IConfiguration _cfg;

        public PromptTemplateService(IConfiguration cfg) => _cfg = cfg;

        public (string system, string user) BuildPrompt(UserProfile user, string query, string mode)
        {
            var modeKey = $"Prompts:{mode}";
            var systemPrompt = _cfg[$"{modeKey}:System"] ?? DefaultSystemPrompt(user);
            var userPrompt = _cfg[$"{modeKey}:User"] ?? DefaultUserPrompt(user, query);

            // Si el modo no existe en config, caemos en el default
            return (systemPrompt, userPrompt);
        }

        private static string DefaultSystemPrompt(UserProfile user) => $"""
        Eres un asistente experto en compras técnicas.
        El usuario pertenece al sistema con email {user.Email}.
        Debes priorizar los proveedores preferidos ({string.Join(", ", user.PreferredVendors ?? [])})
        y evitar los bloqueados ({string.Join(", ", user.BlockedVendors ?? [])}).
        Responde en tono profesional y breve.
        """;

        private static string DefaultUserPrompt(UserProfile user, string query) => $"""
        El usuario busca información sobre "{query}".
        Sus intereses principales son {string.Join(", ", user.FavoriteTags ?? [])}.
        Genera una respuesta concisa y útil.
        """;
    }
}
