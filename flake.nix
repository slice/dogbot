{
  inputs = {
    lifesaver.url = "github:slice/lifesaver";
    nix-filter.url = "github:numtide/nix-filter";
    nixpkgs.follows = "lifesaver/nixpkgs";
  };

  outputs = { lifesaver, flake-utils, nix-filter, nixpkgs, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
      in (pkgs.lib.attrsets.recursiveUpdate (lifesaver.lib.${system}.mkFlake
        ({ python, pkgs, ... }: {
          name = "dogbot";
          path = ./.;
          propagatedBuildInputs = with python.pkgs; [
            asyncpg
            hypercorn
            (python.pkgs.callPackage ./nix/quart.nix { })
            python-dateutil
            geopy
            pillow
            timezonefinder
          ];
          pythonPackageOptions.format = "pyproject";
          hardConfig = {
            bot_class = "dog.bot:Dogbot";
            config_class = "dog.config:DogConfig";
            extensions_path = "./dog/ext";
          };
        })) {
          packages.web = nixpkgs.legacyPackages.${system}.buildNpmPackage rec {
            name = "dogbot-web";
            version = "0.0.0";

            npmDepsHash = "sha256-t903c1mov02Pec7p/IGsSlIOHlN36aaCBllGxcD/4ao=";

            postInstall = ''
              echo "replacing $out with create-react-app build artifacts"
              mv -v $out/lib/node_modules/dogbot-web/build/* $out/
              echo "removing $out/lib"
              rm -r $out/lib
            '';
            src = nix-filter.lib {
              root = ./web;
              include =
                [ "src" "public" ./web/package.json ./web/package-lock.json ];
            };
          };
        }));
}
