using Api.Data;
using Api.Services;
using Microsoft.AspNetCore.Mvc;

namespace Api.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class ProductsController : ControllerBase
    {
        private readonly IProductRepository _productRepo;

        public ProductsController(IProductRepository productRepo)
        {
            _productRepo = productRepo;
        }

        [HttpGet("search")]
        public async Task<IActionResult> Search([FromQuery]  string q, [FromQuery] int limit = 10, CancellationToken ct = default)
        {
            var items = await _productRepo.SearchAsync(q, limit, ct);
            return Ok(items);
        }

    }
}
