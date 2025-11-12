using Api.Data;
using Api.Embeddings;
using Api.Llm;
using Api.Services;
using Azure.Storage.Queues;
using MongoDB.Driver;

var builder = WebApplication.CreateBuilder(args);

// Mongo
var mongoCfg = builder.Configuration.GetSection("Mongo");
var client = new MongoClient(mongoCfg["ConnectionString"]);
builder.Services.AddSingleton<IMongoDatabase>(client.GetDatabase(mongoCfg["Database"]));
builder.Services.AddSingleton<IProductRepository, MongoProductRepository>();

// Embeddings + LLM
builder.Services.AddSingleton<IEmbeddingProvider>(_ => new HashingEmbeddingProvider(
    builder.Configuration.GetValue("Rag:EmbeddingDimensions", 256)));
builder.Services.AddSingleton<ILlmClient, FakeLlmClient>();

// Services
builder.Services.AddSingleton<RagService>();
builder.Services.AddSingleton<RecommendationService>();

// Queue (Azurite)
var storage = builder.Configuration.GetSection("Storage");
var qOptions = new QueueClientOptions { MessageEncoding = QueueMessageEncoding.Base64 };
var qClient = new QueueClient(storage["QueueConnectionString"], storage["QueueName"], qOptions);
builder.Services.AddSingleton(qClient);
builder.Services.AddSingleton<PromptTemplateService>();


// Controllers
builder.Services.AddControllers();
var app = builder.Build();

app.MapControllers();
app.Run();

public partial class Program { }

