using Api.Domain;
using Api.Services;
using Microsoft.AspNetCore.Mvc;

public record ChatRequest(UserProfile User, string Prompt);
namespace Api.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class ChatController : ControllerBase
    {
        private readonly RagService _rag;
        public record ChatRequest(UserProfile User, string Prompt, string Mode = "friendly");

        public ChatController(RagService rag) { 
            _rag = rag;
        }

        [HttpPost]
        public async Task<IActionResult> Ask([FromBody] ChatRequest req, CancellationToken cancellationToken = default)
        {
            var answer = await _rag.AskAsync(req.Prompt, req.User, req.Mode, cancellationToken);
            return Ok(new { answer });
        }
    }
}
