{
  inputs = {
    lifesaver.url = "path:/Users/slice/src/prj/lifesaver";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { lifesaver, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      lifesaver.lib.${system}.mkFlake ({ python, pkgs, ... }: {
        name = "dogbot";
        path = ./.;
        propagatedBuildInputs = with python.pkgs; [
          asyncpg
          hypercorn
          (python.pkgs.callPackage ./nix/quart.nix { })
          python-dateutil
          geopy
          pillow
        ];
        pythonPackageOptions.format = "pyproject";
      }));
}
