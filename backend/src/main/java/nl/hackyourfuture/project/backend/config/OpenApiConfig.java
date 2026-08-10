package nl.hackyourfuture.project.backend.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.servers.Server;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI backendOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("HackYourFuture Final Project Backend API")
                        .description("REST API for the HackYourFuture final project.")
                        .version("0.0.1"))
                .servers(List.of(
                        new Server().url("http://localhost:8080").description("Local development")
                ));
    }
}