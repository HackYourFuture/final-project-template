package nl.hackyourfuture.project.backend.user;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import nl.hackyourfuture.project.backend.user.dto.*;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
@Tag(name = "Users", description = "Operations on user accounts")
public class UserController {

    private final UserS ervice userService;

    @GetMapping
    @Operation(summary = "List all users", description = "Returns every user account currently stored.")
    @ApiResponse(responseCode = "200", description = "The list of users")
    public List<UserResponse> getUsers() {
        return userService.getAllUsers();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create a new user", description = "Registers a new user account and returns it with its generated id.")
    @ApiResponse(responseCode = "201", description = "The user was created")
    @ApiResponse(
            responseCode = "400",
            description = "The request body is invalid",
            content = @Content(schema = @Schema(implementation = ProblemDetail.class))

    )
    public UserResponse createUser(@Valid @RequestBody UserRequest request) {
        return userService.createUser(request);
    }

    @PutMapping("/{id}")
    @Operation(summary = "Update an existing user", description = "Replaces the details of the user with the given id.")
    @ApiResponse(responseCode = "200", description = "The updated user")
    @ApiResponse(
            responseCode = "400",
            description = "The request body is invalid",
            content = @Content(schema = @Schema(implementation = ProblemDetail.class))
    )
    public UserResponse updateUser(
            @Parameter(
                    description = "ID of the user to update",
                    example = "effe1126-329f-4f31-942c-31bc0be4d672"
            )
            @PathVariable UUID id,
            @Valid @RequestBody UserRequest request) {
        return userService.updateUser(id, request);
    }
}
