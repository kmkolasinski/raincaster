help: ## Print this message and exit
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z%_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2 | "sort"}' $(MAKEFILE_LIST)



install: ## Install the package for development
	pip install uv
	uv pip install -e .[dev]

test:  ## Run unit tests
	pytest tests/


clean:  ## Clean up build artifacts
	rm -r build/  2> /dev/null || true
	rm -r src/build/  2> /dev/null || true
	rm -r src/raincaster.egg-info/  2> /dev/null || true
	rm -r dist/ 2> /dev/null || true

precommit: ## Run precommits without actually commiting
	SKIP=no-commit-to-branch pre-commit run --all-files

.ONESHELL:
release: ## Create a new tag for release.
	@echo "WARNING: This operation will create s version tag and push to github"
	@echo "         Update version in pyproject.toml before running this command"
	@echo "         and provide same tag value here."
	@read -p "Version? (provide the next x.y.z semver) : " TAG
	@git add .
	@git commit -m "release: version $${TAG} 🚀" --no-verify
	echo "creating git tag : $${TAG}"
	@git tag $${TAG}
	@git push -u origin HEAD --tags
	@echo "Github Actions will detect the new tag and release the new version."
