using Api.Services;
using Microsoft.AspNetCore.Mvc;

namespace Api.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class RecommendationsController : ControllerBase
    {
        private readonly RecommendationService _recommendationService;
        public RecommendationsController(RecommendationService recommendationService)
        {
            _recommendationService = recommendationService;
        }

        [HttpGet("similar")]
        public async Task<IActionResult> Similar([FromQuery] string term, [FromQuery] int k = 5, CancellationToken cancellationToken = default)
        {
            var items = await _recommendationService.SimilarAsync(term, k , cancellationToken);
            return Ok(items);
        }
    }
}
