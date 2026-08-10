package nl.hackyourfuture.project.backend.user.dto;
import io.swagger.v3.oas.annotations.media.Schema;
import nl.hackyourfuture.project.backend.user.User;

import java.util.UUID;

public record UserResponse(
        @Schema(example = "A7E3ABB2-461F-4BE7-8B94-45A8B2AE7BA2")
        UUID id,
        @Schema(example = "user@example.com")
        String email
) {
    public static UserResponse from(User user) {
        return new UserResponse(
                user.getId(),
                user.getEmail()
        );
    }
}
